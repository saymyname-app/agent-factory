# Registre des catégories de défauts

Intent (Benjamin, ses mots, 22/10/2026 13:12 Paris) : « qu'on trouve une
méthode, là, maintenant, pour que ça n'arrive plus, que tous ces
problèmes-là ne puissent récidiver et ne réarriver sous une autre forme.
Enfin, il faut qu'on puisse prévoir. » ; puis, relayé le 25/10 15:13 Paris :
« Reponds pour moi que je suis Ok pour tes recommandations pour toutes
decisions à prendre. »
Mechanism (interprétation de l'agent, af-npz9v1.25) : la méthode cible
minimale de l'étude B (`research/2026-10-22-causes-racines-incidents.md`,
§ 6). Un correctif d'usine nomme sa catégorie, cherche les autres
occurrences de la même catégorie et les corrige, et pose ou complète le
contrôle automatique qui attrapera la suivante. Ce registre ne crée aucune
porte de Benjamin et n'autorise aucun refactor sans défaut (ADR-0017).

Du 15 au 22/10/2026, environ 70 réparations de l'usine se ramènent à trois
catégories, revenues chacune 5 à 7 fois : chaque correctif réparait l'endroit
observé et écrivait le reste « hors périmètre ». Les correctifs qui n'ont pas
récidivé sont ceux qui ont posé un contrôle de toute la catégorie (#619,
#688, #690, #692).

## Qui lit ce registre

- `bin/factory-fix-preflight --class <code>` : affiche l'invariant et les
  occurrences ouvertes, lance les commandes du champ `Contrôle`, refuse une
  catégorie absente d'ici (le correctif crée alors son entrée dans sa
  branche).
- `bin/pr-autopilot` et le job CI « Maintenance form » : n'arment pas la
  fusion d'une PR de maintenance de l'usine (branche `fix/…` ou
  `do-work/…`), et la tiennent rouge, sans ses lignes de maintenance ; leur
  forme a une seule source, `docs/DELIVERY.md`, « Where else? ». Ils lisent
  ici les catégories, les règles et leur point de passage.
- `python3 lib/defect_classes.py count --since <date>` : les PR fusionnées
  de chaque catégorie depuis une date, lues sur ces mêmes lignes. C'est la
  mesure de la méthode : une catégorie qui revient alors qu'elle a un
  contrôle signale un contrôle incomplet, on complète le contrôle et on
  rouvre l'entrée ici, pas un ticket.
- `python3 lib/defect_classes.py count --by-rule --since <date>` : par
  règle concrète et par mois (Paris), les premières corrections, les
  répétitions prévues et les glissements (af-56yoam.1). Les PR fusionnées
  du 22/10 au 23/11/2026 sont reclassées dans
  `docs/defect-rules-baseline.tsv` ; une PR plus récente est lue sur sa
  ligne `Règle :`, obligatoire depuis af-56yoam.2 pour un correctif.
  `bin/factory-weekly`
  en tire sa section « Récidives par règle ».

Intent (Benjamin, ses mots, 23/11/2026 17:19 Paris, sur l'objectif D1) :
« Oui, les trois ».
Mechanism (interprétation de l'agent, af-56yoam.1) : une famille range 3 à
30 règles différentes, donc compter par famille ne dit pas si une règle
revient (lecture de 152 PR le 23/11). L'unité de la mesure est la règle
concrète : une phrase vérifiable par du code, un identifiant stable, son
point de passage unique. Une répétition est **prévue** quand un « où
ailleurs » antérieur a ouvert un ticket pour ce site, ou qu'elle suit un
découpage planifié ; c'est un **glissement** quand la règle avait déjà une
correction fusionnée et revient. Une règle `<CODE>.autre` range les
défauts isolés d'une famille : elle ne glisse jamais, et trois PR de même
cause en font une règle nommée.

Objectif D1, figé le 23/11/2026 à 19:50 Paris (commentaire sur af-56yoam).
Intent (Benjamin, ses mots, 23/11/2026 19:41 Paris) : « Fait », à la
proposition de lancer un juge aveugle et d'appliquer la nouvelle forme de
D1 si l'accord atteint 70 %. Le juge s'est accordé à 90 % sur « glissement
ou non » (20 PR). Mechanism (interprétation de l'agent, af-56yoam.5) :

1. la part des PR de défaut qui sont des glissements : 86/140 (61 %) en
   novembre 2026, du 1er au 23, dans la base ; au plus 30 % du 01/12 au
   20/12/2026 ;
2. zéro glissement sur une règle **fermée**, celle dont la fonction unique
   est livrée : sa ligne porte `Fermée le <AAAA-MM-JJ> par #<PR>.` après
   son passage. Un glissement sur une règle fermée rouvre sa fonction
   unique : on ne lui ajoute pas un cas ;
3. revue le 21/12/2026 (af-56yoam.4).

Cette forme remplace celle de af-56yoam.1 (18 règles à zéro, plafond de 43
glissements par mois). `lib/defect_classes.py` la calcule (`d1`) et
`bin/factory-weekly` la juge chaque semaine.

## Format

Une catégorie par titre `## CODE — titre`, et quatre champs, chacun sur une
ligne `- Champ : valeur` (la suite d'une valeur longue est indentée de deux
espaces) :

- `Invariant` : la règle en une phrase ;
- `Contrôle` : le test ou lint qui tient la catégorie, chaque commande entre
  accents graves (`python3 …`, `bash …`), ou `aucun — <pourquoi>` ;
- `Occurrences` : les PR connues de la catégorie ;
- `Ouvertes` : les occurrences encore présentes dans le code et leurs Beads,
  ou `aucune connue`.

Et le champ `Règles` : la ligne `- Règles :`, puis une règle concrète par
ligne `` - `<CODE>.<règle>` : <phrase vérifiable>. Passage : <point de
passage unique, ou aucun>. `` indentée de deux espaces (sa suite de quatre),
suivie de `Fermée le <AAAA-MM-JJ> par #<PR>.` quand la PR qui livre sa
fonction unique est fusionnée.
L'identifiant ne change plus une fois écrit : la base de référence et les
PR le citent.

`tests/defect-classes-test.py` refuse une entrée incomplète, une règle sans
phrase ou sans passage, ou rangée sous une autre catégorie. Une catégorie
nouvelle s'ajoute ici, dans la PR du correctif qui la découvre.

## P — Processus ou durée sans propriétaire ni budget mesuré

- Invariant : Tout ce qu'un outil lance meurt avec lui, quelle que soit la
  façon dont il finit ; tout délai vient d'une mesure.
- Règles :
  - `P.own` : Tout processus qu'un outil, un ordre ou un test lance meurt
    avec son propriétaire, quelle que soit la façon dont celui-ci finit.
    Passage : `lib/bounded_process.py` pour le Python de `bin/` et `lib/`,
    `lib/ci_test_reaper.py` pour les tests ; le bash, les formules et les
    processus détachés restent hors passage.
  - `P.budget` : Toute attente ou tout appel a un budget, et ce budget vient
    d'une mesure faite sous la charge réelle, pas d'un chiffre écrit à la
    main. Passage : `lib/test_budgets.py` pour les tests de ticket ; aucun
    pour les ordres et les outils.
  - `P.load` : Le coût d'une passe, d'un ordre, d'un test ou d'un lecteur ne
    croît pas avec l'état (une lecture par élément, des lectures en série,
    une relecture complète) et ne prend de l'hôte que sa part. Passage :
    `lib/host_slots.py` pour les exécutions lourdes ; aucun pour les
    lectures du suivi.
  - `P.proc-gone` : Une lecture de l'état d'un processus (procfs) traite sa
    disparition comme sa fin, jamais comme une erreur. Passage : aucun.
  - `P.autre` : Défaut isolé de la famille, sans règle nommée. Passage :
    aucun.
- Contrôle : `python3 tests/bounded-process-test.py`,
  `python3 tests/project-launch-test.py`, `python3 tests/test-budgets-test.py`,
  `bash tests/agent-wait-polling-test.sh`,
  `bash tests/mayor-context-guard-test.sh`,
  `python3 tests/factory-observe-test.py LiveObservationTest.test_a_mail_unanswered_within_its_timeout_is_deferred_to_the_next_pass`,
  `bash tests/factory-watchdog-test.sh`,
  `python3 tests/idle-ready-work-wake-test.py IdleReadyWorkWakeTest.test_a_hung_notification_is_bounded_without_changing_wake_cooldown`,
  `bash tests/ci-run-tests-leftover-test.sh`,
  `python3 tests/regression-host-queue-test.py RegressionHostQueue.test_a_file_that_leaves_a_process_alive_is_red_and_the_process_is_killed`,
  `python3 tests/regression-host-queue-test.py RegressionHostQueue.test_a_ticket_s_green_has_the_budget_of_the_whole_series`,
  `python3 tests/host-slots-test.py`,
  `python3 tests/tdd-step-test.py TddStepTest.test_green_kills_what_the_regression_leaves_alive_and_keeps_its_verdict`,
  `python3 tests/spec-integration-test.py SpecIntegrationTest.test_a_control_kills_what_it_leaves_in_a_session_of_its_own_and_keeps_its_verdict`,
  `python3 tests/project-launch-test.py ProjectLaunchTest.test_the_sweep_stops_a_program_whose_trial_has_ended_though_its_folder_is_there`,
  `python3 tests/project-launch-test.py ProjectLaunchTest.test_every_tool_that_runs_a_branch_s_commands_in_a_tree_of_its_own_holds_its_trial_lock`,
  `python3 tests/project-launch-test.py ProjectLaunchTest.test_the_sweep_stops_a_product_whose_test_reaper_was_killed_with_its_test`,
  `python3 tests/project-launch-test.py ProjectLaunchTest.test_a_launch_ends_with_its_owner_while_its_product_repository_cannot_be_read`,
  `bash tests/factory-guard-time-budget-test.sh`,
  `bash tests/trial-lock-held-test.sh`,
  `bash tests/planning-artifacts-close-test.sh`,
  `python3 tests/factory-observe-test.py LiveObservationTest.test_the_beads_sessions_and_pull_requests_are_read_together_beads_once`,
  `bash tests/factory-watchdog-test.sh` (cas 1c),
  `bash tests/factory-guard-runtime-worktree-test.sh` (cas 5),
  `bash tests/escalation-door-test.sh` (budget du balayage)
  — complet pour les commandes Python bornées de `bin/`, `lib/` et
  `tests/cockpit-criteria/` : un seul lanceur (`lib/bounded_process.py`)
  ouvre une session et tue son groupe au délai, et aussi quand l'appelant
  meurt avant (un garde lit un tube dont l'appelant est le seul écrivain,
  af-8cfygl) ; le lint refuse toute nouvelle invocation directe et tient
  chaque existante dans la liste datée `config/bounded-process-exceptions.tsv`,
  et refuse toute session ouverte hors du lanceur qui n'est pas détachée
  exprès, avec son motif, dans `config/detached-process-exceptions.tsv`. Le second test tient les
  propriétaires de `project-launch` dans ces trois dossiers. Le troisième tient
  les délais mesurés des tests d'un ticket et de l'ordre convoy-advance
  (`config/test-budgets.json`, étude C T3), pas les autres délais écrits à
  la main. Le quatrième refuse une attente de formule qui peut atteindre les
  cinq minutes sans `gc runtime heartbeat`. Le cinquième tue le groupe d'un
  reset ou d'un mail Mayor bloqué et tient leur sémantique de reprise. Le
  contrôle `factory-watchdog-test.sh` injecte un `gc` bloqué dans le vrai
  `factory-watchdog`, prouve que son budget interne rend avant celui de
  l'order et tue tout son groupe de processus, puis tient le délai d'incident
  ticket à 30 min de silence réel, retenu par une passe `convoy-advance` en
  cours au plus son `pass_seconds` mesuré, sans casser l'override
  d'exploitation (af-xgd1rd) ;
  le dernier tient la notification de `idle-ready-work-wake` dans son budget
  sans changer son réveil ni son cooldown. Les deux derniers tiennent les
  tests eux-mêmes : `bin/ci-run-tests` et la régression du Cockpit lancent
  chaque fichier sous `lib/ci_test_reaper.py`, sous-faucheur (subreaper) qui
  tue ce qu'un fichier laisse vivant en finissant, le nomme et le fait
  échouer (af-i9llwm). Le dernier tient la limite unique de l'hôte : au
  plus N exécutions lourdes ensemble (`lib/host_slots.py`), l'attente d'une
  place n'étant ni un échec ni une part d'un budget (af-lsbqj9). Les deux
  derniers tiennent les commandes de test et de régression qu'une branche
  apporte elle-même à `bin/tdd-step` et `bin/spec-integration` : elles
  tournent sous le faucheur de l'usine (`--keep-status`), qui tue ce
  qu'elles laissent sans changer leur verdict, et la vérification d'une
  étape de `tdd-step` est elle-même sous-faucheuse de tout ce qu'elle lance
  (af-8mjdai). Les deux derniers tiennent ce qui survit à l'essai lui-même
  tué : `bin/tdd-step` et `bin/spec-integration` tiennent un verrou d'essai
  sur leur arbre tant qu'ils vivent (`lib/trial_lock.py`), et
  `bin/project-launch sweep` arrête tout programme remis à init dont l'arbre
  est sous un essai au verrou libre ; tout outil qui lance les commandes
  d'une branche sous le faucheur doit tenir ce verrou (af-3vcqd3). Le
  dernier tient ce qui survit au faucheur lui-même tué avec son test : le
  faucheur donne au test un dossier temporaire à lui (`TMPDIR`), sous un
  verrou d'essai qu'il tient tant qu'il vit et qu'il retire avec le dossier
  en finissant ; le sweep arrête le produit remis à init dont l'arbre est
  sous ce dossier au verrou libre, et reconnaît les copies de
  `project-launch` qu'un test y a faites (af-23j8a8). Le lint de
  `tests/bounded-process-test.py` refuse enfin une liste d'arguments de
  kill(1) qui donne un groupe (un pid négatif calculé) avant `--` :
  procps-ng 4.0.4 lit `kill -9 -11176` comme kill(-1, SIGKILL) ; un groupe
  se signale par `os.killpg` (af-23j8a8). Le dernier tient l'arrêt d'un
  lancement dont la copie ne peut être vérifiée : les processus marqués de
  son identité sont arrêtés quand même, et la copie dont git ne lit plus le
  dépôt source (en cours de retrait) est reconnue par son fichier de
  propriété (af-u7df4z). Le dernier tient le coût de la sauvegarde des
  branches de `factory-guard` : une branche égale à origin n'y coûte aucun
  processus (af-abozjt). Le dernier tient les villes d'essai : tout test
  qui tue les processus de son essai par chemin tient le verrou d'essai de
  ce chemin tant qu'il vit (`isolated_city_hold_trial`,
  `tests/lib/isolated-city.sh`, ou `trial_lock.hold` en Python), et le sweep
  arrête le processus remis à init dont le `GC_HOME` est dans un essai au
  verrou libre ; `bin/local-only-tests` lance chaque test sous le faucheur
  comme `bin/ci-run-tests` (af-myowqa). Le dernier tient le coût d'un
  ordre déclenché à chaque fermeture de bead : `planning-artifacts-close`,
  sans convoi fermé depuis sa dernière passe finie, s'arrête après une
  seule lecture courte du suivi (af-ktxsfi) ; sa passe complète tient
  dans son budget, lui-même dans le délai de l'ordre, et l'ordre ne part
  plus à chaque fermeture de bead (af-c8m2gh). Le dernier tient la relève
  en direct de `factory-observe` : les beads non fermés lus une seule
  fois, lus avec les sessions et les PR en même temps (af-ufug19). Le
  cas 1c de `factory-watchdog-test.sh` tient ses sections 1 à 9 : les
  lectures qui ne dépendent de rien d'autre dans la passe partent
  ensemble (af-1oo6zy). Le cas 5 de `factory-guard-runtime-worktree-test.sh`
  refuse un test d'ascendance par branche distante (af-9dcuga) ; celui du
  balayage d'`escalation-door-test.sh` tient qu'un budget épuisé ne commence
  plus de page et sort à 0 (af-kvi78c).
- Occurrences : #624, #628, #629, #630, #631, #636, #647, #657, #658, #661,
  #667, #694, #696, #705, #706, #708, #710, #713, #721 ; copies orphelines du
  22/10 (sans PR) ; af-kky570 ; af-npz9v1.46 ; af-npz9v1.26 ; af-30zwwu ;
  af-95zqgx ; af-d3dj4j ; af-ll4hju ; af-bl2jyj ; af-p4rdr7 ; af-6go1ss ;
  af-npz9v1.55.1 ; af-npz9v1.55.2 ; af-npz9v1.55.3 ; af-8cfygl (régression
  survivant à sa passe tuée, ordre convoy-advance à 90 min sans compter une
  attente par exécution) ; af-i9llwm (porte synthétique « expires » laissée
  par chaque régression du Cockpit, 23 vivantes le 11/11) ; af-8a246o
  (plafonds d'attente de 3 s des actions opérateur et de 1,5 s du réveil
  idle-ready-work-wake, rouges sous une charge de 37 à 39 sur 8 cœurs ;
  budget complet de la régression du Cockpit dépassé, relevé par la mesure) ;
  af-lsbqj9 (PR 840 à 860 : des outils sains rouges sous une charge de 30 à
  100 sur 8 CPU, budgets relevés trois fois, chaque correctif bornant un
  seul outil ; arbres tdd-step, copies project-launch et régressions
  spec-integration tournaient hors du verrou de `ci-run-tests`, lui-même
  dans un `/tmp` que le bac à sable des rôles remplace : une seule limite
  hôte les tient tous) ; af-8mjdai (charge de 81 sur 8 cœurs le 12/11 :
  les cockpits laissés par la régression d'arbres `tdd-step` de branches
  antérieures au faucheur sondaient leur ville synthétique hors du pool, un
  depuis 43 h, 0,8 cœur chacun) ; af-hafyxx (budget vert de 1260 s mesuré
  sur les seuls verts finis dedans : la famille « runs », 24 classes, n'y
  tenait jamais ; un vert a désormais le budget de la série entière) ;
  af-3vcqd3 (af-p4v2q2 : un `bin/cockpit run` de l'arbre `tree-10` d'un
  `tdd-step` tué, remis à systemd --user, a sondé sa ville synthétique 61 h :
  l'arbre restait là, le sweep le gardait ; les arbres de fusion de
  `spec-integration`, sous `$XDG_RUNTIME_DIR`, n'étaient même pas regardés) ;
  af-23j8a8 (le produit d'un test lancé dans une session à lui, son
  faucheur tué avec le test, passait à systemd --user dans un dossier
  temporaire du test encore là, sans marque, sans dossier disparu ni
  essai ; le nettoyage du test de ce correctif, `kill -9 -<groupe>`, a tué
  par kill(-1) tous les processus du compte du runner GitHub : le lot 5
  perdu deux fois, sans journal) ; af-u7df4z (le produit d'Essai, lancé
  depuis la copie du Cockpit qui le possède, survivait quand le garde le
  lisait pendant que l'arrêt de ce Cockpit retirait la copie : git échouait,
  le garde partait sans rien tuer ; le faucheur de
  `tests/cockpit-criteria-test.py` l'a trouvé, PR #899 et #901, 17/11) ;
  af-abozjt (sous une charge de 15 à 35 sur 8 cœurs, la sauvegarde des
  branches de `factory-guard` lançait un awk et un `git rev-parse` pour
  chacune de ~860 branches, 117 s des 150 s du budget, et les sections
  suivantes n'étaient plus vérifiées ; la liste des sessions de la ville
  était relue une fois par rig) ; af-myowqa (trois villes d'essai, essai
  tué avant son nettoyage, tournaient sous systemd --user jusqu'à 8 h 52,
  Dolt à 20-49 %, charge 20 sur 8 cœurs, six ordres hors budget le 20/11 ;
  trois autres oubliées depuis 8 à 21 jours ; le contrôle nocturne
  `bin/local-only-tests` lançait ces tests sans faucheur) ; af-ktxsfi
  (`planning-artifacts-close`, lancé à chaque fermeture de bead, relisait
  tous les convois fermés, l'état des convois marqués et leurs documents
  même quand aucun convoi ne s'était fermé : 12 s pour la seule liste à une
  charge de 20, budget de 30 s coupé sept fois de suite à une charge de 8,
  af-f8aglj) ;
  af-c8m2gh (la même passe complète, forcée au moins une fois l'heure,
  durait 25 à 50 s à une charge de 5 à 13 sous un budget de 30 s : jamais
  finie, son relevé ne bougeait plus et chaque fermeture de bead la
  relançait, coupée, cinq échecs en trois heures le 21/11 ; ordre passé à
  un cooldown de deux minutes, budget de 150 s dans un délai de 180 s) ;
  af-ufug19 (`factory-observe live`, dernière section de
  `factory-watchdog`, lisait l'un après l'autre trois listes de beads,
  les sessions et les PR, chaque lecture à environ 4 s quel que soit
  son contenu : 73 s à une charge de 11 à 15, après 49 s de sections
  1 à 9, budget de 150 s coupé sept fois de suite, af-ri69fn) ;
  af-1oo6zy (les sections 1 à 9 de `factory-watchdog` lisaient encore
  l'une après l'autre portes, PR, workflows fermés, `gh auth`, rigs puis
  quarantaines, sessions puis convois : 61 s d'une passe de 69 s à une
  charge de 28, la relève en direct coupée trois passes de suite, cinq
  échecs de l'ordre en trois heures le 22/11 ; lues ensemble, 31 s ->
  13 s sur la ville) ; af-9dcuga (la section runtime-worktrees de
  `factory-guard` lançait un `git merge-base` par branche distante, ~900,
  pour une worktree hors d'origin : 66 s du budget de 150 s à une charge
  de 12, sept sections non vérifiées ; un seul `rev-list`, 0,2 s) ;
  af-kvi78c (`escalation-door sweep` : 87 s à une charge de 9 contre un
  ordre à 60 s ; budget de 90 s, ordre à 180 s).
- Ouvertes : les invocations directes antérieures hors des occurrences de
  l'étude B sont nommées une par une, avec leur date et leur motif, dans
  `config/bounded-process-exceptions.tsv` ; une vingtaine de délais écrits à
  la main restent à l'étude C. Un test qui fait ses dossiers hors de
  `TMPDIR` (un chemin `/tmp/...` écrit en dur) reste hors du verrou de son
  faucheur. Aucune autre invocation
  Python bornée ni aucun lanceur de produit sans propriétaire n'est connu
  hors du contrôle.

## I — Impasse d'état : un arrêt ou une attente sans sortie codée

- Invariant : Chaque arrêt, chaque parcage et chaque option proposée à
  Benjamin a un chemin de code qui fait bouger le ticket, ou dit « reste à
  Benjamin, par telle porte ».
- Règles :
  - `I.repair-resume` : Un ticket arrêté ou parqué en attente d'une
    réparation liée reprend une fois, par une seule transition, quand la
    livraison de cette réparation est prouvée dans l'arbre qu'il teste.
    Passage : aucun (T4 d'af-56yoam : une machine d'états dans
    `lib/convoy_state.py`).
  - `I.convoy-unblock` : Une sortie codée vaut pour tout état de même forme,
    jamais pour un convoi, un ticket ou un historique nommé. Passage :
    aucun (T5 : un lint refuse un identifiant de ticket ou de convoi écrit
    en dur).
  - `I.option-exit` : Chaque option proposée à Benjamin, et chaque levée
    d'arrêt, a un consommateur codé qui fait bouger le ticket comme elle
    l'annonce. Passage : aucun ; contrôle
    `tests/state-exit-contract-test.py`.
  - `I.bound-fact` : Une borne de reprises ne compte que ce que le ticket a
    fait, jamais un fait de l'usine ou une reprise ouverte par une réponse.
    Passage : aucun.
  - `I.frozen-succession` : Le test gelé d'un autre ticket ne change que
    par une succession autorisée, décidée en un seul endroit. Passage :
    `check_amend` de `bin/tdd-step` (des exceptions y sont encore écrites
    en dur ; T5 : `succession_allowed()`).
  - `I.route-deadline` : L'attente d'un rôle (relecteur, Evaluator) compte
    son délai et sa borne depuis la prise de la route, jamais depuis son
    envoi. Passage : aucun (T9 : `route_deadline()`).
  - `I.ticket-own-changes` : Un changement apporté par la base fusionnée
    n'est jamais imputé au ticket. Passage : aucun (T9 :
    `ticket_own_changes()`).
  - `I.answer-binding` : Une réponse de Benjamin compte pour la demande
    qu'elle tranche et pour elle seule : ni perdue, ni consommée par une
    autre reprise. Passage : aucun (T9 : `answer_for()`).
  - `I.green-stop` : Un arrêt décidé sur un vert (critère déjà vert, rouge
    non reproduit, preuve déplacée) a une sortie codée : rejouer, puis
    clore ou reprendre une fois. Passage : aucun.
  - `I.stale-verdict` : Un verdict ou un arrêt périmé (contrat changé,
    nouvelle pointe) est rejugé ou renvoyé à son auteur, jamais tenu pour
    terminal. Passage : aucun.
  - `I.place-cap` : Une reprise comptée ou un tour de correction attend une
    place sous le plafond N, dans l'ordre d'arrivée, et la prend. Passage :
    aucun.
  - `I.delivery-exit` : Un refus de la chaîne de livraison (file de fusion,
    branche impoussable) a une sortie codée : retour à l'auteur ou constat
    déposé une fois. Passage : aucun.
  - `I.patch-refusal` : Un repair rédigé que la porte de patch refuse est
    noté là où il a été rédigé et arrête son convoi. Passage : aucun.
  - `I.integration-conflict` : La reprise de la branche protégée en conflit
    dans une branche d'intégration a une sortie codée. Passage : aucun.
  - `I.autre` : Défaut isolé de la famille, sans règle nommée. Passage :
    aucun.
- Contrôle : `python3 tests/state-exit-contract-test.py` — complet : sa table
  tient la liste fermée des raisons d'arrêt et de parcage, la cardinalité de
  chaque liste d'options proposée à Benjamin, et exige pour chaque ligne une
  transition prouvée ou la porte humaine qui la garde ; une exception sans
  date échoue. Les preuves de comportement qu'elle nomme comprennent
  `python3 tests/convoy-state-test.py ConvoyStateTest.test_a_stopped_unfavorable_judgement_from_an_older_contract_is_invalidated_and_rejudged`,
  `python3 tests/code-review-test.py CodeReviewTest.test_an_unfavorable_judgement_from_the_previous_contract_is_rejudged_once_at_the_same_tip`,
  `python3 tests/tdd-step-test.py TddStepTest.test_an_ambiguous_short_successor_does_not_name_either_ticket`,
  `python3 tests/convoy-advance-resumes-stops-end-test.py ConvoyAdvanceTest.test_a_factory_technical_request_waits_for_every_linked_repair_s_delivery_proof_then_resumes_once`,
  `python3 tests/convoy-advance-resumes-stops-end-test.py ConvoyAdvanceTest.test_a_maintenance_answer_waits_for_its_linked_repair_s_delivery_then_resumes_once`,
  `python3 tests/convoy-advance-resumes-stops-end-test.py ConvoyAdvanceTest.test_an_evaluation_without_result_resumes_once_after_its_linked_factory_repair_is_delivered`,
  `python3 tests/convoy-advance-resumes-stops-end-test.py ConvoyAdvanceTest.test_an_evaluation_outage_resumes_once_after_its_linked_factory_repair_is_delivered`,
  `python3 tests/convoy-state-test.py ConvoyStateTest.test_migrate_repair_resume_accepts_only_the_exact_legacy_history_and_changes_only_the_last_cause`,
  `python3 tests/convoy-advance-resumes-stops-end-test.py ConvoyAdvanceTest.test_a_legacy_delivered_repair_at_the_unblocked_bound_is_migrated_and_sent_once`,
  `python3 tests/convoy-advance-resumes-stops-end-test.py ConvoyAdvanceTest.test_the_exact_delivered_C2b_release_becomes_one_native_repair_resume ConvoyAdvanceTest.test_the_C2b_release_rejects_nearby_state_and_incomplete_delivery_proof`,
  `python3 tests/convoy-advance-resumes-stops-end-test.py ConvoyAdvanceTest.test_the_repaired_D_result_is_judged_without_another_author_resume ConvoyAdvanceTest.test_the_repaired_D_result_release_rejects_nearby_state_and_incomplete_delivery ConvoyAdvanceTest.test_the_repaired_C2b_result_is_judged_without_another_author_resume ConvoyAdvanceTest.test_the_repaired_C2b_result_release_rejects_nearby_state_and_incomplete_delivery`,
  `python3 tests/convoy-advance-resumes-stops-end-test.py ConvoyAdvanceTest.test_the_cleaned_C2b_evaluation_request_is_rebuilt_once_without_an_author_resume`,
  `python3 tests/convoy-state-test.py ConvoyStateTest.test_withdraw_ticket_writes_its_gate_no_op_outcome_note_and_closed_status_in_one_tracker_write`,
  `python3 tests/convoy-advance-resumes-stops-end-test.py ConvoyAdvanceTest.test_the_exact_answered_R8_is_closed_without_merge_then_its_control_runs_green ConvoyAdvanceTest.test_the_exact_R8_close_retry_finishes_after_its_durable_native_lift ConvoyAdvanceTest.test_the_exact_answered_R8_closes_without_merge_and_one_repair_follows_a_red_control ConvoyAdvanceTest.test_the_R8_close_release_rejects_nearby_state_and_option_b`,
  `python3 tests/convoy-advance-red-replay-test.py`,
  `python3 tests/convoy-advance-red-cleared-test.py`,
  `python3 tests/tdd-step-intermittent-red-test.py`,
  `python3 tests/convoy-advance-resumes-stops-end-test.py ConvoyAdvanceTest.test_a_ticket_stopped_all_green_on_one_run_of_each_test_is_resumed_once_without_an_answer`,
  `python3 tests/convoy-advance-resumes-stops-end-test.py ConvoyAdvanceTest.test_a_malformed_legacy_resume_is_left_to_the_incident_door_without_crashing`,
  `python3 tests/convoy-advance-resumes-stops-end-test.py ConvoyAdvanceTest.test_a_factory_repair_is_taken_up_and_tested_before_its_resume_is_consumed_once`,
  `python3 tests/outcome-evaluation-every-dataset-test.py`,
  `python3 tests/outcome-evaluation-outdated-stop-test.py`,
  `bash tests/factory-work-dispatch-test.sh`,
  `python3 tests/convoy-advance-resumes-stops-end-test.py ConvoyAdvanceTest.test_a_ticket_finished_without_its_green_at_the_tip_goes_back_to_its_author_once`,
  `python3 tests/convoy-advance-resumes-stops-end-test.py ConvoyAdvanceTest.test_a_linked_repair_answered_to_be_fixed_in_the_convoy_goes_back_to_the_ticket_s_author_once ConvoyAdvanceTest.test_a_ticket_lifted_before_its_link_resumes_once_its_repair_is_answered_to_be_fixed_in_the_convoy`. Sa même table tient chaque
  fonction de `bin/convoy-advance` qui publie un repair rédigé par la porte
  de patch : un refus de la porte y est noté là où le repair a été rédigé et
  arrête le convoi, ou la fonction est une exception datée qui nomme son
  Bead (`test_every_publisher_of_a_drafted_repair_gives_a_patch_door_refusal_an_exit`).
  Les courses réponse/retrait qui
  pourraient consommer une réponse sont tenues par
  `python3 tests/convoy-advance-resumes-stops-end-test.py ConvoyAdvanceTest.test_an_evaluation_stop_answered_while_its_request_is_cleared_is_not_resumed ConvoyAdvanceTest.test_a_removed_stage_stop_answered_while_its_request_is_cleared_is_not_resumed ConvoyAdvanceTest.test_a_grouped_answer_recorded_while_changed_parkings_are_re_raised_is_applied_first`
  et `python3 tests/convoy-advance-review-evaluation-correction-test.py ConvoyAdvanceTest.test_a_code_review_stop_answered_while_its_request_is_cleared_is_not_resumed`.
  Le refus de la file de fusion GitHub est tenu par
  `bash tests/pr-autopilot-merge-queue-refusal-test.sh`.
- Occurrences : #635, #637, #650, #653, #662, #666, #672, #673, #679, #682,
  #687, #702, #704, #709, #711, #712, #718 ; af-npz9v1.44 ; af-npz9v1.47 ; af-npz9v1.48 ; af-npz9v1.35 ;
  af-bf0e7d (`evaluation_outage` repris une fois après la livraison prouvée
  de sa maintenance liée) ; af-e0n71v (`evaluation_no_result` refusait sa
  maintenance liée et restait arrêté) ; af-o5ritb (la livraison d'une réparation liée
  reprend par sa propre cause bornée, sans épuiser le seau `unblocked`) ; af-qjw5lm
  (la réparation livrée sur `main` ne libère la reprise qu'après sa présence
  vérifiée dans la pointe d'intégration testée) ; af-62duoi (la migration
  historique de `unblocked` refusait l'ancien arrêt d'évaluation avant de
  pouvoir convertir son dernier signal de réparation) ; af-wjhpx9 (une
  reprise `answered` ajoutée après cette conversion rendait de nouveau
  l'historique illisible) ; af-npz9v1.57 (l'entrée C2b déjà comptée et
  parquée n'avait plus son lien de réparation après la livraison des deux
  réparations qui permettaient sa reprise) ; af-npz9v1.59 (les levées
  historiques légitimes empêchaient la libération du résultat réparé de C2b,
  et le résultat réparé de D n'avait aucune libération symétrique) ;
  af-npz9v1.60 (l'option répondue
  « clore R8 sans fusion » n'avait aucune porte native et relançait un auteur) ;
  af-npz9v1.66 (la requête de la seconde route Evaluator de C2b avait été
  effacée avant le correctif, puis son parcage empêchait de la reconstruire) ;
  af-npz9v1.67 (`open-resume` avait effacé la sortie au sommet de C2b alors
  que sa dernière reprise en conservait la copie, donc la transition exacte
  ne reconnaissait pas l'état réel) ; af-3p6iz7 (un repair red_check sans
  commit dont le rouge ne se reproduit pas n'avait aucune clôture codée : R10
  restait parqué ; la règle générale rejoue le contrôle et clôt sans fusion
  au vert) ; af-6vhm6r (la même règle ignorait un rouge déjà retiré au vert
  par `spec-integration merge` après un déplacement de pointe : R10 restait
  ouvert sans rouge à rétablir ; ce vert est gardé comme preuve et le repair
  se clôt sans fusion dessus) ; af-68sgzq (un repair rédigé par l'Evaluator
  de fin et refusé par la porte de patch était renvoyé à chaque passe,
  `convoy-advance` en échec sans rien noter : le refus est noté sur la story
  ou le constat et l'Outcome Evaluation s'arrête, `outcome_repair_refused`) ;
  af-ip0nrq (un `story_unobservable` causé par l'usine, un seul jeu ouvert
  sur les 95 déclarés, n'avait que les options « Planning Run » et « retirer
  la story » : une maintenance liée à l'arrêt le lève par code une fois
  livrée et l'évaluation repart au même commit, sans tour de fin) ;
  af-oa2ci4 (un repair qui ne fait que déplacer une preuve, R12, avait tous
  ses critères verts au rouge : `criterion_already_green` l'arrêtait et seule
  la clôture « satisfait » restait, qui ne fusionne rien ; prouvé par
  `python3 tests/tdd-step-proof-move-test.py` et
  `python3 tests/convoy-advance-resumes-stops-end-test.py ConvoyAdvanceTest.test_a_repair_that_moves_a_proof_stopped_all_green_is_resumed_once_without_an_answer_nor_a_round_of_the_end ConvoyAdvanceTest.test_a_repair_of_a_behavior_stopped_all_green_stays_stopped_with_the_operator`) ;
  af-vm0vua (la réponse de Benjamin à une Planning Exception antérieure,
  portée par le même bead, passait pour la réponse à la demande de l'arrêt :
  R12 restait arrêté sans demande ni reprise ; une réponse ne compte plus
  que pour la demande de l'arrêt lui-même, `stop_answer`, prouvé par
  `python3 tests/convoy-advance-resumes-stops-end-test.py ConvoyAdvanceTest.test_an_answer_to_an_earlier_planning_exception_does_not_hold_a_proof_moved_resume ConvoyAdvanceTest.test_a_proof_moved_stop_answered_after_its_own_request_is_not_resumed`) ;
  af-mmefvq (un arrêt d'Outcome Evaluation tient son commit seul, mais sa
  demande restait sur la liste de Benjamin une fois la porte passée à un
  autre commit, et une maintenance liée ne pouvait plus le lever : `settle`
  range l'arrêt périmé sous `lifts` (`outdated_by`), retire sa demande sans
  réponse et évalue la nouvelle pointe, prouvé par
  `python3 tests/outcome-evaluation-outdated-stop-test.py`) ;
  af-fv8ca4 (la réponse « Corriger par maintenance sur main » levait le
  parcage avant que sa réparation soit liée, R13, et une passe qui avait lu
  le ticket avant le lien le levait encore, R20 et R22 : ces tickets
  reprenaient sans leur correctif ; la réponse attend la livraison de la
  réparation liée et `lift-park` relit le lien à son écriture, prouvé par
  `python3 tests/convoy-advance-resumes-stops-end-test.py ConvoyAdvanceTest.test_a_maintenance_answer_waits_for_its_linked_repair_s_delivery_then_resumes_once`) ;
  af-1row55 (R16 af-yv2g3n sorti « terminé » à un commit de jeu de données
  après son vert : la revue et l'évaluation attendaient un ticket vert à la
  pointe, rien ne le renvoyait ; `bin/ticket-exit` refuse cette sortie et
  `convoy-advance` renvoie à son auteur, cause `returned`, celle déjà
  enregistrée, prouvé par
  `python3 tests/ticket-exit-test.py TicketExitTest.test_finished_is_refused_when_the_green_was_proven_before_the_head_commit`
  et `python3 tests/convoy-advance-resumes-stops-end-test.py ConvoyAdvanceTest.test_a_ticket_finished_without_its_green_at_the_tip_goes_back_to_its_author_once`) ;
  af-t8hycw (R20 af-3l6hbt restait lié à af-8fk8nz, une réparation de code
  présent sur la seule branche d'intégration, que Benjamin a fait corriger
  « dans le convoi » : aucune PR vers main ne la livrerait, le ticket
  l'attendait pour toujours ; `convoy-advance` rend la réparation au ticket,
  `return-technical-repair`, et son auteur reprend pour la faire, prouvé par
  `python3 tests/convoy-advance-resumes-stops-end-test.py ConvoyAdvanceTest.test_a_linked_repair_answered_to_be_fixed_in_the_convoy_goes_back_to_the_ticket_s_author_once ConvoyAdvanceTest.test_a_ticket_lifted_before_its_link_resumes_once_its_repair_is_answered_to_be_fixed_in_the_convoy`) ;
  af-batj8g (R23 af-ujme6p arrêté `criterion_already_green` sur un seul
  passage d'un test rouge 7 fois sur 8, et la Planning Exception de son
  auteur n'offrait pas « le rouge est réel » : `tdd-step red` rejoue un test
  qui passe jusqu'à k exécutions et ne le dit vert que s'il passe à chacune ;
  `convoy-advance` reprend une fois, cause `red_replayed`, un arrêt décidé
  sur une seule exécution, prouvé par
  `python3 tests/tdd-step-intermittent-red-test.py` et
  `python3 tests/convoy-advance-resumes-stops-end-test.py ConvoyAdvanceTest.test_a_ticket_stopped_all_green_on_one_run_of_each_test_is_resumed_once_without_an_answer`) ;
  af-u21377 (R11 af-ksan9t, reprise `behind` comptée sous un plafond plein,
  attendait depuis cinq heures : chaque place libérée allait à la reprise
  d'un ticket rangé avant lui dans le convoi ; une reprise comptée et pas
  envoyée prend la place suivante, la plus ancienne d'abord, dans le convoi
  et entre convois, prouvé par
  `python3 tests/convoy-advance-resumes-stops-end-test.py ConvoyAdvanceTest.test_a_counted_resume_waiting_for_a_place_takes_the_next_one_before_a_ticket_earlier_in_the_convoy ConvoyAdvanceTest.test_a_counted_resume_waiting_in_another_convoy_takes_the_next_place_before_this_one_s_resume`) ;
  af-sdd8gr (le tour de correction de R18 af-gnplfy parti sans regarder le
  plafond N : Gas City lui a donné la place que la reprise comptée de R11
  af-ksan9t attendait depuis 07:01 ; un tour attend une place libre, compté
  et daté, après les reprises et avant les démarrages, et un tour envoyé
  tient sa place jusqu'à ce qu'une session prenne le ticket, prouvé par
  `python3 tests/correction-round-test.py CorrectionRoundTest.test_a_round_with_no_free_author_place_waits_counted_and_is_sent_once_a_place_frees`
  et `python3 tests/convoy-advance-review-evaluation-correction-test.py ConvoyAdvanceTest.test_a_correction_round_waits_for_a_free_author_place_then_holds_it_until_a_session_takes_the_ticket`) ;
  af-strhoy (l'option « a » « Relancer un tour de réparation » de la
  demande « non conforme » n'avait aucun consommateur : la réponse restait
  sur le bead, `end_stop` n'était jamais retiré et le convoi ne pouvait plus
  être livré ; `convoy-advance` lit la réponse « a » postérieure à la
  demande et appelle `convoy-state lift-end-stop`, qui garde l'arrêt sous
  `end_stop_lifts` et compte un tour au-delà de la borne ; la table du
  contrôle tient désormais les trois raisons `END_STOPS` et les trois
  options de `non_conforme_request`, prouvé par
  `python3 tests/convoy-stops-fixture-city-test.py ConvoyStopsOnTheFixtureCity.test_the_answer_a_to_the_non_conforme_request_lifts_the_stop_and_grants_exactly_one_round_more ConvoyStopsOnTheFixtureCity.test_the_answers_b_and_c_to_the_non_conforme_request_lift_nothing ConvoyStopsOnTheFixtureCity.test_an_answer_a_given_before_the_non_conforme_request_lifts_nothing`) ;
  af-nih6m6 (la file de fusion GitHub retirait PR #889, son commit combiné
  rouge, et `pr-autopilot` la réarmait au même head à la passe suivante,
  7 fois en 80 minutes, chacune un run `merge_group` complet : ce refus
  n'avait aucune sortie codée ; une tête refusée n'est plus remise en file,
  son ticket repart à son auteur, sinon un bead est déposé une fois, prouvé
  par `bash tests/pr-autopilot-merge-queue-refusal-test.sh`).
- Ouvertes : exceptions datées du 29/10/2026, tenues une par une par le
  contrôle : `criterion_already_green` reste au Planning Run, sauf
  le repair qui ne fait que déplacer une preuve (af-oa2ci4 : `tdd-step red`
  ne l'arrête plus, et `convoy-advance` reprend une fois, cause
  `proof_moved`, celui arrêté avant) et l'arrêt décidé sur une seule
  exécution de chaque test (af-batj8g, cause `red_replayed`) ;
  `outcome_evaluation_no_result` et `outcome_evaluation_outage` ne repartent
  qu'à une nouvelle pointe d'intégration ; `story_unobservable` reste au
  Planning Run, sauf l'arrêt qu'une maintenance de l'usine liée lève par code
  (af-ip0nrq) ; datée du 09/11/2026, `outcome_repair_refused` ne repart
  qu'à une nouvelle pointe d'intégration. Datés du 09/11/2026, les repairs
  écrits par le code dont la porte de patch refuse le brouillon sont encore
  renvoyés à chaque passe : `settle_red` (af-dtt6dn), `settle_item_repairs`
  (af-uz9bh9), `settle_acceptance` (af-k369au). Elles sont retirées de la
  table dès qu'une transition codée remplace cette porte (étude B § 4.2,
  af-npz9v1.27). Hors de la table, constatée le 10/11/2026 (af-nh4c1t) :
  la reprise de la branche protégée en conflit dans une branche
  d'intégration n'a pas de sortie et refait échouer `convoy-advance` à
  chaque passe (`docs/CONVOY_ADVANCE.md`, « What these stops leave open ») ;
  le choix de sa sortie est une règle de méthode, proposée à Benjamin
  (af-le1aas, ADR-0029 point 6). Constatée le 12/11/2026 (af-u21377) : un
  tour de correction (`bin/correction-round`) part sans regarder le plafond
  N et prend la place qu'une reprise comptée attend (af-sdd8gr).

## D — Doublure, instrument ou vue partielle qui ne se comporte pas comme le réel

- Invariant : Un faux outil refuse ce que le vrai refuse ; un instrument qui
  juge est étalonné sur un cas connu avant de servir ; on juge l'état
  résultant, jamais un morceau.
- Règles :
  - `D.fake-tool` : Un faux `bd`, `gc` ou `gh` refuse ce que le vrai refuse
    et rend la même forme (pages, drapeaux, état). Passage : aucun (T6 :
    des transcriptions enregistrées sur les vrais outils) ; contrôle
    `tests/fake-tool-contract-test.py`.
  - `D.isolated-cockpit` : Le Cockpit d'essai et la cité isolée ont leurs
    propres portes, verrous et état, et servent ce que le réel sert.
    Passage : `bin/cockpit-isolated`.
  - `D.resulting-state` : On juge l'état résultant entier (graphe, liste
    complète des fichiers, suivi relu après l'écriture), jamais un morceau.
    Passage : aucun.
  - `D.merged-per-github` : « Fusionnée » se lit comme GitHub le dit (PR
    fusionnée qui tient la tête), jamais par la seule ascendance Git, qu'une
    fusion squash ne donne pas. Passage : aucun.
  - `D.eval-datasets` : L'Évaluateur juge sur les jeux du ticket, dont ceux
    de la démonstration et ceux que la branche apporte. Passage : aucun.
  - `D.calibrated-judge` : Un instrument qui juge (relecteur, tolérance d'un
    test) est étalonné sur un cas connu ; une règle vérifiable par du code
    n'est pas laissée à un jugement. Passage : aucun.
  - `D.adoption-trial` : L'essai d'adoption d'un rôle passe par le même
    transport et les mêmes états que le réel, et ne touche que le
    fournisseur ciblé. Passage : `bin/role-adoption-trial`.
  - `D.autre` : Défaut isolé de la famille, sans règle nommée. Passage :
    aucun.
- Contrôle : `python3 tests/account-home-lint-test.py`,
  `python3 tests/fake-tool-contract-test.py`,
  `python3 tests/cockpit-isolated-https-test.py`,
  `python3 tests/cockpit-isolated-door-locks-test.py`,
  `python3 tests/evaluation-capacity-test.py`,
  `bash tests/gh-unsupported-subcommand-guard-test.sh`,
  `python3 tests/reversibility-test.py`,
  `bash tests/pr-autopilot-project-hold-test.sh`,
  `bash tests/factory-maintain-test.sh`,
  `bash tests/factory-guard-merged-branch-backup-test.sh` — complet pour le dossier
  personnel et les faux exécutables `bd`/`gc` : le second tient en CI la
  liste fermée des 27 faux, rejoue la limite d'un argument sur chacun, la
  fermeture d'un bloqué sur les 11 qui écrivent l'état et les huit formes
  de dépendance sur les deux qui les acceptent ; il refuse aussi dans `bin/`
  le drapeau retiré `bd create --set-metadata`, que les faux en ligne avaient
  accepté en silence. Sur l'hôte de l'usine il
  étalonne d'abord le même oracle sur les vrais `bd`/`gc` dans une cité
  jetable ; les 16 faux de lecture ou de transport sans état mutable ont
  chacun leur exception datée dans le contrôle (af-npz9v1.28). Le troisième
  lance les trois décors résultat d'Essai derrière le proxy d'identité et
  tient leur suivi jetable. Le quatrième prouve que deux lancements du
  cockpit isolé côte à côte ont chacun leurs verrous des portes (proposition,
  escalade) et leur répertoire d'exécution, jamais ceux de l'hôte. Le suivant
  tient l'admission partagée des
  produits d'évaluation et refuse qu'une cité isolée lise les lancements, le
  verrou ou les attestations de l'usine en service ; il tient aussi le
  sous-montage des attestations en lecture seule quand leur état isolé vit
  sous le parent inscriptible `$HOME/.cache`. Le dernier refuse dans
  `bin/` et `lib/` les formes de `gh` absentes du vrai : `gh pr
  update-branch`, et `--jq` suivi de `--arg`, que le faux `gh` de la
  relance d'un contrôle rouge acceptait (af-toyety). Les deux suivants
  tiennent la lecture des fichiers d'une PR par ses deux portes de
  `pr-autopilot` : la réversibilité lit la liste page par page, jamais le
  diff entier que GitHub refuse au-delà de 300 fichiers (le faux `gh` le
  refuse aussi), et refuse de juger une liste plus courte que la PR ; une
  liste illisible n'arme pas une PR comme une liste vide (af-u0uuhr).
  Les deux derniers tiennent « fusionnée » lu comme GitHub le dit, pas
  par la seule ascendance Git, qu'une fusion squash ne donne jamais :
  `prune-merged-branches` élague une branche dont une PR fusionnée tient
  la tête, et `factory-guard` ne repousse pas sur origin une telle branche
  que GitHub a supprimée à la fusion (af-tdpbg1).
- Occurrences : #566, #618, #641, #648, #656, #664, #665, #669, #671, #674,
  #675, #676, #680, #689, #690, #692, #699, #700, #714, #715 ; af-vf51g6 ;
  af-dtsy06 ; af-h6nyqc ; af-toyety ; af-yxxa68 ; af-33j358 ; af-u0uuhr
  (`bin/reversibility-check` lisait le diff entier d'une PR : HTTP 406 sur
  les 325 fichiers de #889, une erreur `pr-autopilot` à chaque passage ;
  la porte des descripteurs de projet prenait une liste illisible pour une
  liste vide) ; af-tdpbg1 (`prune-merged-branches` ne voyait fusionnée
  qu'une branche ancêtre de `main` : 858 branches locales jamais élaguées ;
  la sauvegarde de `factory-guard` recréait sur origin, minutes après sa
  fusion, chaque branche squash que GitHub venait de supprimer).
- Ouvertes : exception datée du 29/10/2026 : la relecture de code par modèle
  n'est pas rejouée sur un cas connu (étude B § 4.3). Elle reste bornée par
  ses citations vérifiées et ses passes ciblées, mais n'est pas déclarée
  étalonnée par ce contrôle déterministe. Aucun faux `bd`/`gc` connu n'est
  hors du contrôle.

## R — Une même règle tenue à deux endroits qui divergent

- Invariant : Une règle, une fonction : un écrivain et son lecteur, ou deux
  outils, lisent la règle au même endroit.
- Règles :
  - `R.ticket-evaluation-proof` : L'écrivain de la Ticket Evaluation et le
    lecteur de fin de ticket lisent la preuve par la même fonction.
    Passage : `evaluation_proven_by_test` de `lib/delivery_rules.py`.
  - `R.close-rule` : Qui peut fermer un ticket du nouveau flux se lit en un
    seul endroit, par tous les outils qui ferment. Passage :
    `bin/convoy-state ticket`.
  - `R.autre` : Une autre règle tenue à deux endroits, sans règle nommée.
    Passage : `lib/delivery_rules.py` quand la paire y est.
- Contrôle : `python3 tests/delivery-rules-test.py` tient les quatre paires
  connues sur leurs fonctions communes ; `bash tests/operator-bd-test.sh`
  tient l'identité `po-agent/<session>` entre l'écrivain opérateur et
  `factory-orphan-sweep` ; `bash tests/dispatch-door-test.sh` tient les
  arêtes `blocks` écrites pour sérialiser les périmètres jusqu'à la dernière
  porte d'admission, avant la création de l'espace de travail ;
  `python3 tests/test-budgets-test.py` tient le délai de la régression complète
  lu par `spec-integration` et `spec-end` sur la même source mesurée ;
  `python3 tests/bead-close-writers-test.py` nomme chaque écriture qui ferme
  un bead dans `bin/` et `lib/` avec ce qu'elle ferme, et
  `bash tests/factory-delivery-guard-test.sh` tient la règle de fermeture
  d'un ticket du nouveau flux lue dans `bin/convoy-state ticket` par
  `factory-delivery-guard` comme par `deliver-close`, et `gc.authorized_by`
  lu comme l'autorité du travail, jamais comme le bead qu'il livre.
- Occurrences : #620, #625, #659, #660, #681, #685, #686, #693, #695, #703,
  #716 ; af-npz9v1.42 ; af-npz9v1.52 ; af-9wnmid ; af-a53dy2 ; af-epwkmn
  (`factory-delivery-guard` lisait `gc.authorized_by` comme le bead livré et
  a fermé hors porte R10 af-30ix43, ce qui a arrêté son convoi ; il rouvre
  ce ticket au statut que ses portes permettent) ; af-lsbqj9 (le verrou
  « une batterie à la fois » de `bin/ci-run-tests` et le plafond de deux
  produits d'évaluation étaient deux règles de charge de l'hôte, chacune
  pour un outil : les deux sont des usages du pool de `lib/host_slots.py`,
  tenu par `python3 tests/host-slots-test.py` et
  `python3 tests/evaluation-capacity-test.py`).
- Ouvertes : les quatre propositions que `factory-delivery-guard` a fermées
  hors de `bin/proposal-door` avant af-epwkmn (af-p1q5pz, af-ze0zan,
  af-pgckwt, af-rmbml9) attendent leur résolution par la porte, af-8a2e9d ;
  `review_replay_due`, `tdd_evidence_piece` et
  `names_in_texts` ont remplacé les trois paires ouvertes de l'étude B § 4.4
  (af-npz9v1.29), et `evaluation_proven_by_test` tient l'écrivain de la
  Ticket Evaluation avec son lecteur de fin de ticket (`lib/delivery_rules.py`,
  af-npz9v1.52, 2026-10-30).

## S — Signal faux ou manquant

- Invariant : Une alerte dit vrai et une situation qui demande quelqu'un
  produit une alerte.
- Règles :
  - `S.load-cut` : Une passe d'ordre coupée ou ralentie par la charge, ou
    qui ne fait que retrouver un constat déjà déposé, est reportée
    (sortie 0) ; seules N passes coupées de suite sont un échec. Passage :
    aucun (chaque ordre code son report ; T9 : `bounded-pass`).
  - `S.watchdog-stall` : Le gardien signale un ticket sans suite si et
    seulement si personne ne le fait bouger ni ne l'attend par choix de
    Benjamin. Passage : `assess_ticket` de `lib/factory_watchdog.py`, avec
    la règle de levée de `lib/delivery_rules.py`.
  - `S.merge-confirmed` : Un état de PR (armée, fusionnée, relancée) n'est
    annoncé qu'une fois relu sur GitHub. Passage : `merge_and_confirm` de
    `lib/merge_confirm.sh` (armer, fusionner, désarmer, relancer). Fermée
    le 2026-11-24 par #933.
  - `S.fixed-deadline` : Un test attend l'événement qu'il éprouve, jamais
    une échéance d'horloge fixe que la charge fait tomber. Passage :
    `isolated_city_wait_for` (`tests/lib/isolated-city.sh`) pour les
    essais en cité isolée ; aucun ailleurs (T9 : `wait_for_event`).
  - `S.alert-dedup` : Une alerte cherche son double parmi tous les beads non
    fermés et ne remonte pas un bead fermé. Passage : aucun ; contrôle
    `tests/alert-dedup-status-test.py`.
  - `S.human-request` : Seul ce qui attend vraiment Benjamin, sur la liste
    fermée d'ADR-0036, lui est présenté comme tel. Passage :
    `bin/escalation-door benjamin`.
  - `S.failure-evidence` : Un échec garde sa preuve (nom du contrôle en
    échec, dossier de l'essai). Passage : aucun.
  - `S.autre` : Défaut isolé de la famille, sans règle nommée. Passage :
    aucun.
- Contrôle : `bash tests/on-order-failed-test.sh`,
  `python3 tests/alert-dedup-status-test.py`,
  `python3 tests/factory-observe-test.py LiveObservationTest`,
  `bash tests/pr-autopilot-armed-not-merged-test.sh`,
  `bash tests/pr-autopilot-transient-retry-test.sh`,
  `bash tests/pr-autopilot-unproven-merge-test.sh`,
  `bash tests/merge-confirm-test.sh`,
  `python3 tests/tdd-step-test.py TddStepTest.test_green_refusal_keeps_the_failing_control_after_long_regression_output`,
  `python3 tests/role-adoption-trial-codex-test.py`,
  `python3 tests/factory-delivery-proof-test.py ClaimedShippedBead`,
  `python3 tests/ticket-graph-publish-test.py TicketGraphPublishBeadModeTest.test_a_mayor_wake_delivered_but_slow_to_answer_is_not_reported_as_lost`,
  `bash tests/factory-watchdog-test.sh`,
  `python3 tests/factory-watchdog-test.py StalledTicketRules`,
  `bash tests/pr-autopilot-time-budget-test.sh`,
  `bash tests/planning-artifacts-close-test.sh`,
  `bash tests/convoy-parent-sweep-test.sh`,
  `bash tests/factory-maintain-test.sh`,
  `bash tests/isolated-city-stop-guard-test.sh`,
  `bash tests/ci-apt-install-test.sh`,
  `python3 tests/bounded-process-test.py BoundedProcessTest.test_an_exception_keeps_its_name_when_lines_move_around_it`,
  `bash tests/trial-lock-held-test.sh`,
  `python3 tests/bounded-process-test.py BoundedProcessTest.test_timeout_kills_the_commands_descendants`,
  `python3 tests/cockpit-stop-test.py StopDriverTest.test_a_reading_begun_before_the_forced_session_stopped_does_not_say_its_assignment_kept` — partiel : le premier
  tient la frontière entre un report explicite (sortie 75, rejoué sans
  alerte) et une vraie panne répétée (bead et page Mayor), et qu'un bead pris
  en réparation ou parqué répond encore à sa panne ; `alert-dedup-status`
  refuse dans `bin/` une recherche d'alerte par titre qui ne lit que les beads
  `open` : elle lit `open,in_progress,blocked,deferred`, ou c'est un balayage
  qui ne ferme que les alertes que personne n'a prises et le dit
  (`# open only:`) ; le deuxième tient
  la collecte VM Beads/Git/GitHub, le silence sur état inchangé, la route
  unique au plus petit propriétaire présent, la preuve durable avant l'alerte,
  sa clé stable de dédoublonnage, la conservation d'une demande humaine, le
  relevé final à +2 h, et qu'une PR que l'usine ne pilote pas (aucun ticket
  tenu ne porte sa branche ni son numéro) ne réveille personne tant qu'aucune
  vérification n'échoue et qu'elle n'est ni fusionnée ni fermée ; le troisième refuse qu'une sortie locale 0 compte comme
  armement sans relecture GitHub et tient la fusion directe au head, à CLEAN et
  au contrôle requis vert ; il relit aussi GitHub après toute demande de fusion
  directe et n'annonce la fusion que si le serveur répond `MERGED`. Le
  contrôle `merge-confirm` tient la table de `merge_and_confirm` : une
  demande acceptée dont la PR reste en file n'est pas « fusionnée », une PR
  relue `MERGED` l'est, une erreur GitHub laisse l'état inconnu et sans
  annonce, et une relance n'est dite faite que si le run relu a redémarré. Le contrôle
  9 du gardien (#688) couvre les tickets que personne ne bouge, pas les autres
  signaux ; `StalledTicketRules` tient qu'un ticket qui attend ce que Benjamin
  a choisi (le Planning Run, une réparation liée encore ouverte) n'est pas
  signalé, par la règle de levée que la passe applique (af-hnh16e). Le quatrième refuse qu'un workflow encore actif ou une demande de
  rerun refusée soit annoncé comme déjà retenté. Le contrôle `tdd-step`
  conserve le début et la fin d'une longue sortie bornée, dont le nom du
  contrôle en échec. Le contrôle `role-adoption-trial-codex` tient la minute de
  stabilité après un réveil Codex proche
  de l'échéance dans une borne fixe et exige qu'un délai dépassé nomme les états
  observés et la demande de réveil ; il refuse aussi que `active` compte comme
  provider-ready quand le premier nudge ne crée aucun rollout, et tient les
  trois dialogues interactifs (mise à jour, confiance du dossier, hooks) hors
  des profils Codex sans opérateur. Le contrôle `factory-delivery-proof` refuse
  qu'un `gc.outcome=pass` d'étape de formule (`gc.step_ref`/`gc.step_id`)
  compte comme livraison annoncée : l'étape qui ouvre la PR n'est pas une
  livraison non prouvée. Le contrôle `factory-observe` et
  `ticket-graph-publish` refusent qu'un `gc mail send` borné, déjà remis mais
  lent à répondre, compte comme perdu : `ticket-graph-publish` rejoue l'envoi
  une fois sous la même clé `--dedup` ; `factory-observe` garde la route en
  attente et la renvoie sous la même clé au passage suivant, et seul un envoi
  refusé par gc ou resté sans réponse trois passages de suite est un échec. Le
  contrôle `factory-watchdog` refuse qu'un passage du gardien coupé par son budget sous la charge,
  ou dont l'observation live n'a pas tenu dans le temps restant, compte comme
  un échec de l'ordre : il est reporté (sortie 0), et seuls trois passages
  coupés de suite sortent 2. Le contrôle `pr-autopilot-time-budget` tient la
  même frontière pour `pr-autopilot`, arrêté en entier sous le délai de son
  ordre. Le contrôle `planning-artifacts-close` la tient pour la fermeture des
  Spec et brouillons : une passe coupée par son budget de 30 s, sous le délai
  de 60 s de son ordre, est reportée (sortie 0) sans rien fermer à moitié, et
  seules trois passes coupées de suite sortent 2. Le contrôle
  `convoy-parent-sweep` la tient pour le balayage des convois : un
  `gc convoy check` coupé par le budget de 90 s du script, sous le délai de
  120 s de l'ordre, est reporté à la fermeture suivante (sortie 0), et seuls trois
  balayages coupés de suite sortent 2. Le contrôle `factory-maintain` refuse
  que `clean-worktrees` signale comme travail perdu la copie non publiée d'un
  ticket en cours dont la session auteure est ouverte, et tient le
  signalement de la copie d'un ticket dont la session est partie. Le contrôle
  `isolated-city-stop-guard` refuse qu'un essai en cité isolée attende sur une
  échéance d'horloge à lui : chaque attente passe par `isolated_city_wait_for`
  (`tests/lib/isolated-city.sh`), qui compte le temps que l'hôte donne à
  l'essai (une seconde à deux fois plus de charge que de CPU compte pour
  moitié, jusqu'à quatre fois le délai écrit) et nomme la charge quand il
  renonce ; il refuse aussi qu'un essai efface son répertoire sans le garder
  quand il a échoué (`isolated_city_keep_failure`). Le contrôle `ci-apt-install` refuse dans `.github/workflows/`
  un `apt-get` hors de `bin/ci-apt-install`, qui passe à l'archive
  principale d'Ubuntu puis à la copie gardée de `config/ci-apt-kept/`
  (vérifiée par son SHA256SUMS) quand le miroir du runner ne répond pas :
  une panne du dépôt de paquets n'est plus un contrôle rouge. Le contrôle
  `bounded-process` nomme chaque exception de
  `config/bounded-process-exceptions.tsv` et
  `config/detached-process-exceptions.tsv` par son fichier et sa fonction
  (`#2` après la première d'une même fonction), jamais par son numéro de
  ligne : une ligne ajoutée ailleurs dans le fichier ne rougit plus un
  travail sans rapport. Le contrôle `cockpit-stop` refuse qu'après un arrêt
  forcé le Cockpit dise une affectation gardée sur une lecture des tickets
  commencée avant que le superviseur ait arrêté la session. Le contrôle
  `trial-lock-held` refuse dans `tests/*.sh` un `timeout <N> bash -c` dont
  le script pose un `trap` : l'échéance fixe peut tomber, sous la charge,
  avant que le piège soit posé ; l'essai dit qu'il est armé, puis le test
  signale son groupe. `bounded-process` fait tomber l'échéance qu'il
  éprouve une fois le descendant né, en la doublant jusqu'à 16 s.
- Occurrences : #651, #679, #688, #717 ; af-npz9v1.50 ; #767 (armement local
  annoncé mais `autoMergeRequest=null`, af-npz9v1.50.1) ; af-ncg9qy ; #778
  (demande directe acceptée localement mais encore `AWAITING_CHECKS`,
  af-nk5nm6) ; af-27yx7q.2.1 ; af-pd6m09 ; af-1l3znv (un workflow encore
  actif ou une demande de rerun refusée était annoncé comme déjà retenté) ;
  af-0rdubb ; af-eyi5wa (l'étape push-and-pr, passée en ouvrant sa PR, signalée
  comme livraison non prouvée) ; af-usvfdb (un mail d'alerte remis mais
  confirmé après le délai de 20 s comptait comme échec du gardien, et le même
  délai faisait écrire « Mayor NOT woken » à `ticket-graph-publish`) ;
  af-onrwp8 (après af-usvfdb, les deux envois d'un même passage restaient sans
  réponse sous load 15m ~34, et un passage ralenti par la charge dépassait le
  budget de 150 s : 3 échecs du gardien sur 9 passages, alertes pourtant
  parties) ; af-pmbhlh (`pr-autopilot` dépassait le délai de 120 s de son
  ordre malgré son budget de 90 s : passé l'arrêt dur, chaque appel restait
  lancé 1 s + 5 s de kill, et rien ne bornait le passage entier ; 2 échecs
  sous load 15m ~30) ; af-p1d8ka (`planning-artifacts-close`, sans budget
  interne, tué trois fois au délai de 60 s de son ordre sous la charge, du 07
  au 10/11/2026) ; af-cbvryy (un `gc convoy check` ralenti par la charge tué
  au délai de 120 s de `convoy-parent-sweep`, le 10/11/2026 à 00:01) ;
  af-mc1u08 (`clean-worktrees` a signalé comme non poussée la copie d'un
  ticket dont l'auteur, session active, n'avait pas encore publié : af-h2boiv
  le 28/10, af-apbds3 le 11/11/2026) ; af-2crkwu (la nuit du 11/11/2026, sous
  une charge de 40 à 100 sur 8 CPU, trois essais en cité isolée arrêtés à leur
  échéance d'horloge fixe en plein parcours, sans rien de cassé, et signalés
  comme régressions) ; af-xcdibe (le 11/11/2026 de 14:28 à 15:45Z, les
  quatre exécutions de la CI de #859 rouges sur `apt-get install
  bubblewrap`, « Temporary failure resolving azure.archive.ubuntu.com »,
  sans défaut dans le changement) ; af-xgd1rd (R16 et R19 du convoi af-strhoy
  sans suite ~8 h le 11/11 sans alerte : la demande de fin de Spec portée par
  le convoi exemptait tous ses tickets, une session d'auteur vivante mais
  oisive après sa sortie comptait comme avancée, et le délai suivait le
  budget d'une passe, 148 min, au lieu de 30 min de silence réel) ;
  af-vy9ajj (le 12/11/2026, #866 et #867, sans rapport entre elles, rouges
  sur `bounded-process` parce que la vérification de fidélité détachée de
  `bin/convoy-advance`, listée à la ligne 3768, avait glissé à 3772 et à
  3780) ; af-hnh16e (le 12/11/2026, le gardien signalait « sans suite » R23
  af-ujme6p, renvoyée au Planning Run par la réponse de Benjamin à sa
  Planning Exception, et R16 af-yv2g3n, qui attendait sa réparation liée
  af-33j358 encore ouverte : la règle de levée du parcage, tenue dans
  `convoy-advance` seul, est partagée par `lib/delivery_rules.py`) ;
  af-65mbq2 (le 13/11/2026, `pr-autopilot` en échec à chaque passe pendant des
  heures pour un seul refus de `deliver-close` : #876, fusionnée dans
  integration/af-fgcw0d sans run de CI possible sur sa tête, comptée en
  erreur d'ordre à chaque passe, et l'alerte nommait le budget de temps de la
  ligne suivante ; le refus est désormais un constat déposé une fois) ;
  af-yzojic (le 13/11/2026, `on-order-failed` ne cherchait l'alerte d'une
  panne que parmi les beads `open` : af-65mbq2, en cours de réparation, n'y
  était plus, et trois alertes en double, af-0965hq, af-uzajg3 et af-to7kkp,
  ont été ouvertes et envoyées au Mayor ; même recherche corrigée dans
  `backup-freshness`, `factory-session-loop-guard`, `factory-watchdog` et
  `factory-maintain`) ; af-hi8i79 (af-7curg1 : `factory-do-work-workspace
  finish` sortait 0 sans URL pour une branche sans commit d'avance sur une
  base qui avait bougé — gh refusait « No commits between » — et
  push-and-pr demandait d'ouvrir à la main une PR vide ; même cas corrigé
  après un rebase qui retire tous les commits) ; af-dbe735 (les 17 et
  18/10/2026, des échecs nocturnes intermittents de `correction-round` et
  `spec-end-review` en cité isolée : le nettoyage effaçait l'essai et rien ne
  restait à diagnostiquer ; #727 ne gardait que `correction-round`, les douze
  autres essais gardent désormais leur dernier échec) ; af-kz2eao (même
  forme que R19 d'af-xgd1rd, au contrôle 1 du gardien : une porte humaine
  vieillie était tue dès que le bead qu'elle bloque, ou le convoi qui le
  suit, avait n'importe quelle demande sur la liste de Benjamin ; seule la
  demande portée par la porte, ou celle de ce bead ou de ce convoi qui nomme
  la porte, la tait désormais) ; af-oa01l3 (après un arrêt forcé, le départ
  d'une session était daté à l'ordre et non à l'arrêt : une lecture commencée
  entre les deux disait « affectation gardée » d'un ticket perdu) ; af-jnvjh5 (le 18/11/2026,
  `factory-observe live` a réveillé le Mayor sept fois de suite pour les
  vérifications de #909, ouverte par une session opérateur, sans rien à
  faire) ;
  af-tjnggf (le 22/11/2026, la file de fusion a refusé #925, sans rapport,
  sous une charge de 12 à 28 : `tests/trial-lock-held-test.sh` arrêtait
  son essai par `timeout 3`, tombé avant que l'essai ait pris son verrou
  et posé son nettoyage, et son dossier restait ; même échéance fixe dans
  `tests/bounded-process-test.py`, qui lisait le pid d'un descendant pas
  encore écrit).
- Ouvertes : af-dc8eqb (`tests/host-slots-test.py`, budget `timeout 3`
  d'un essai d'une seconde, qui peut couper sous la charge).

## L — Ticket rouvert réclamable par un ouvrier lancé pour un autre

- Invariant : Un ticket de travail n'est pris que par la session lancée pour
  lui : un outil qui le rouvre sans le relancer lui retire sa route
  (`gc.routed_to`) et la session de son dernier lancement (`gc.session_id`,
  `gc.session_name`), par `lib/work_route_release.sh`.
- Règles :
  - `L.route-release` : Un outil qui rouvre un ticket sans le relancer lui
    retire sa route et sa session. Passage : `lib/work_route_release.sh`.
- Contrôle : `python3 tests/work-route-release-test.py` — complet : chaque
  écriture de `bin/` et des formules qui rouvre un bead passe par
  `lib/work_route_release.sh`, ou est nommée dans sa table avec pourquoi elle
  ne rouvre aucun travail lancé ; les retraits eux-mêmes sont prouvés par
  `bash tests/escalation-door-test.sh`,
  `bash tests/on-session-stranded-test.sh`,
  `bash tests/pr-autopilot-ticket-rejection-test.sh` et
  `bash tests/factory-delivery-guard-test.sh`.
- Occurrences : af-asymry (le 11/11/2026, la session lancée pour af-fv8ca4 a
  pris af-8fk8nz, rouvert par `escalation-door repondre` avec
  `gc.routed_to=factory-worker` et sa session, et l'a repris sur la mauvaise
  branche ; le balayage des orphelins de Gas City rend la route à un ticket
  ouvert, sans assigné, qui garde `gc.work_branch` et sa session).
- Ouvertes : aucune connue.

## C — Confinement : un rôle confiné écrit ce qu'une session libre exécute

- Invariant : Une session confinée (relecteur, Evaluator, tout rôle lancé par
  `bin/delivery-role-sandbox`) n'écrit rien qu'une session non confinée
  exécute ou lit comme consigne : réglages et hooks des fournisseurs, serveurs
  MCP, mémoire, réglages et scripts de gc, répertoires de travail des autres
  sessions, formules.
- Règles :
  - `C.sandbox` : Un rôle confiné n'a en écriture rien qu'une session libre
    exécute ou lit comme consigne. Passage : `bin/delivery-role-sandbox`.
- Contrôle : `python3 tests/delivery-role-sandbox-config-test.py`
- Occurrences : af-q55qqx (F7 de l'analyse du 16/11/2026 : `~/.claude` monté
  en écriture, un relecteur pouvait y poser un hook ; même voie par
  `.claude.json`, `~/.codex/config.toml`, `.gc/settings.json`, `.gc/scripts`,
  `.gc/agents`, `.gc/worktrees`, `.beads/formulas`), corrigé ici.
- Ouvertes : `~/.cache` et `~/.local/state` restent en écriture (caches
  d'outils et états exécutés ensuite par des sessions libres) ; les sessions
  d'écriture tournent sans confinement avec le jeton propriétaire. Les deux
  relèvent de J11 (configuration et identité par rôle), af-q55qqx.

## H — Historique d'un ticket écrasé par une écriture

- Invariant : Une écriture sur un bead existant ajoute à ses notes
  (`--append-notes`), elle ne les remplace jamais (`--notes`) ; seul
  `bd create --notes` reste permis, un bead neuf n'ayant rien à perdre.
- Règles :
  - `H.append-notes` : Une écriture sur un bead existant ajoute à ses notes
    et ne les remplace jamais. Passage : aucun ; contrôle
    `tests/bead-notes-append-test.py`.
- Contrôle : `python3 tests/bead-notes-append-test.py`,
  `bash tests/deliver-close-test.sh`
- Occurrences : af-2cuvon (le 11/11 puis le 17/11/2026, la fermeture
  d'af-icbz5h par `bin/deliver-close` a remplacé toutes ses notes par le
  motif de fermeture ; même écriture dans `bin/factory-delivery-guard`,
  `bin/factory-watchdog`, `bin/factory-session-loop-guard`, l'ouverture de
  PR de `mol-do-work` et `mol-polecat-commit`, la fermeture des étapes de
  toutes les formules et la règle d'AGENTS.md), corrigé ici.
- Ouvertes : aucune connue.

## W — Outil lancé depuis une copie de travail qui s'adresse à la copie au lieu de l'usine

- Invariant : Un outil de `bin/` ou `lib/` qui nomme une ville à gc
  (`gc --city`) prend FACTORY_ROOT, sinon `lib/factory_city.py` : depuis la
  copie de travail d'un agent, c'est le dossier principal de l'usine, jamais
  la copie, à qui manque le `city.provider.toml` généré.
- Règles :
  - `W.city-root` : Un outil qui nomme une ville à gc prend la racine de
    l'usine, jamais la copie de travail d'où il est lancé. Passage :
    `lib/factory_city.py`.
- Contrôle : `python3 tests/factory-city-test.py`,
  `bash tests/factory-work-dispatch-test.sh`
- Occurrences : af-zry5xu (le 17/11/2026, `bin/proposal-door` lancé par un
  agent depuis sa copie af-x7xg4s a créé af-oa01l3 sans pouvoir le lancer :
  `bin/factory-work-dispatch` passait sa propre copie en FACTORY_ROOT, et gc
  n'y trouvait pas `city.provider.toml` ; même défaut dans
  `bin/dispatch-door`, `bin/convoy-advance`, `lib/convoy_state.py`,
  `bin/convoy-graph`, `bin/ticket-graph-publish`, `bin/project-standards`,
  `lib/factory_build_gates.py`), corrigé ici.
- Ouvertes : aucune connue.

## A — Autre

- Invariant : Aucun invariant commun : une PR rangée ici dit pourquoi elle
  n'entre dans aucune autre catégorie ; trois PR de même cause font une
  catégorie nouvelle.
- Règles :
  - `A.reload-code` : Un processus long de l'usine recharge le code fusionné
    qui le change, et dit la révision qu'il a chargée. Passage :
    `bin/factory-guard` (redémarrage du Cockpit).
  - `A.autre` : Défaut isolé sans famille ni règle nommée. Passage : aucun.
- Contrôle : aucun — catégorie de tri.
- Occurrences : #619, #622, #639, #655, #677 ; tests nocturnes #634, #663,
  #670, #707 ; af-8hdaf1 (`bin/pr-autopilot` : la lecture de tout
  l'historique coupée sous charge suspendait la clôture des PR fusionnées et
  le renvoi des PR en conflit, que la lecture des beads ouverts, déjà faite,
  suffisait à décider ; garde-fou `bash tests/pr-autopilot-cut-history-test.sh`) ;
  af-gh3cxi (`tests/factory-guard-exec-bit-test.sh` lançait cinq fois les
  seize sections du garde pour en vérifier une seule, la première ; il dépassait
  120 s sous charge 44 tant que ces sections lisaient l'état réel, corrigé
  par #793 ; le test s'arrête désormais à `invariants`) ;
  af-lmjqkf (`mol-dog-stale-db`, formule vapor du pack bd/dolt : son chien
  exécute l'étape telle que `gc bd formula show` l'affiche, sans rendre ses
  variables, et Bash recevait `{{warn_threshold}}` littéral ; copie locale
  dans `formulas/` aux seuils écrits en dur ; garde-fou
  `bash tests/mol-dog-stale-db-formula-test.sh`, qui refuse aussi tout jeton
  de gabarit dans une formule vapor de `formulas/`).
- Ouvertes : aucune connue.
