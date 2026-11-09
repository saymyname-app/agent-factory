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
- `bin/pr-autopilot` : n'arme pas la fusion d'une PR de maintenance de
  l'usine (branche `fix/…` ou `do-work/…`) sans ses trois lignes
  `Catégorie :`, `Où ailleurs :`, `Contrôle de catégorie :`
  (`docs/DELIVERY.md`, « Maintenance de l'usine »).
- `python3 lib/defect_classes.py count --since <date>` : les PR fusionnées
  de chaque catégorie depuis une date, lues sur ces mêmes lignes. C'est la
  mesure de la méthode : une catégorie qui revient alors qu'elle a un
  contrôle signale un contrôle incomplet, on complète le contrôle et on
  rouvre l'entrée ici, pas un ticket.

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

`tests/defect-classes-test.py` refuse une entrée incomplète. Une catégorie
nouvelle s'ajoute ici, dans la PR du correctif qui la découvre.

## P — Processus ou durée sans propriétaire ni budget mesuré

- Invariant : Tout ce qu'un outil lance meurt avec lui, quelle que soit la
  façon dont il finit ; tout délai vient d'une mesure.
- Contrôle : `python3 tests/bounded-process-test.py`,
  `python3 tests/project-launch-test.py`, `python3 tests/test-budgets-test.py`,
  `bash tests/agent-wait-polling-test.sh`,
  `bash tests/mayor-context-guard-test.sh`,
  `python3 tests/factory-observe-test.py LiveObservationTest.test_a_hung_mail_is_bounded_and_remains_pending`,
  `bash tests/factory-watchdog-test.sh`,
  `python3 tests/idle-ready-work-wake-test.py IdleReadyWorkWakeTest.test_a_hung_notification_is_bounded_without_changing_wake_cooldown`
  — complet pour les commandes Python bornées de `bin/`, `lib/` et
  `tests/cockpit-criteria/` : un seul lanceur (`lib/bounded_process.py`)
  ouvre une session et tue son groupe au délai ; le lint refuse toute
  nouvelle invocation directe et tient chaque existante dans la liste
  datée `config/bounded-process-exceptions.tsv`. Le second test tient les
  propriétaires de `project-launch` dans ces trois dossiers. Le troisième tient
  les délais mesurés des tests d'un ticket et de l'ordre convoy-advance
  (`config/test-budgets.json`, étude C T3), pas les autres délais écrits à
  la main. Le quatrième refuse une attente de formule qui peut atteindre les
  cinq minutes sans `gc runtime heartbeat`. Le cinquième tue le groupe d'un
  reset ou d'un mail Mayor bloqué et tient leur sémantique de reprise. Le
  contrôle `factory-watchdog-test.sh` injecte un `gc` bloqué dans le vrai
  `factory-watchdog`, prouve que son budget interne rend avant celui de
  l'order et tue tout son groupe de processus, puis tient le délai d'incident
  ticket sur le `pass_seconds` mesuré sans casser l'override d'exploitation ;
  le dernier tient la notification de `idle-ready-work-wake` dans son budget
  sans changer son réveil ni son cooldown.
- Occurrences : #624, #628, #629, #630, #631, #636, #647, #657, #658, #661,
  #667, #694, #696, #705, #706, #708, #710, #713, #721 ; copies orphelines du
  22/10 (sans PR) ; af-kky570 ; af-npz9v1.46 ; af-npz9v1.26 ; af-30zwwu ;
  af-95zqgx ; af-d3dj4j ; af-ll4hju ; af-bl2jyj ; af-p4rdr7 ; af-6go1ss ;
  af-npz9v1.55.1 ; af-npz9v1.55.2 ; af-npz9v1.55.3.
- Ouvertes : les invocations directes antérieures hors des occurrences de
  l'étude B sont nommées une par une, avec leur date et leur motif, dans
  `config/bounded-process-exceptions.tsv` ; une vingtaine de délais écrits à
  la main restent à l'étude C. Aucune autre invocation
  Python bornée ni aucun lanceur de produit sans propriétaire n'est connu
  hors du contrôle.

## I — Impasse d'état : un arrêt ou une attente sans sortie codée

- Invariant : Chaque arrêt, chaque parcage et chaque option proposée à
  Benjamin a un chemin de code qui fait bouger le ticket, ou dit « reste à
  Benjamin, par telle porte ».
- Contrôle : `python3 tests/state-exit-contract-test.py` — complet : sa table
  tient la liste fermée des raisons d'arrêt et de parcage, la cardinalité de
  chaque liste d'options proposée à Benjamin, et exige pour chaque ligne une
  transition prouvée ou la porte humaine qui la garde ; une exception sans
  date échoue. Les preuves de comportement qu'elle nomme comprennent
  `python3 tests/convoy-state-test.py ConvoyStateTest.test_a_stopped_unfavorable_judgement_from_an_older_contract_is_invalidated_and_rejudged`,
  `python3 tests/code-review-test.py CodeReviewTest.test_an_unfavorable_judgement_from_the_previous_contract_is_rejudged_once_at_the_same_tip`,
  `python3 tests/tdd-step-test.py TddStepTest.test_an_ambiguous_short_successor_does_not_name_either_ticket`,
  `python3 tests/convoy-advance-resumes-stops-end-test.py ConvoyAdvanceTest.test_a_factory_technical_request_waits_for_every_linked_repair_s_delivery_proof_then_resumes_once`,
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
  `python3 tests/convoy-advance-resumes-stops-end-test.py ConvoyAdvanceTest.test_a_malformed_legacy_resume_is_left_to_the_incident_door_without_crashing`,
  `python3 tests/convoy-advance-resumes-stops-end-test.py ConvoyAdvanceTest.test_a_factory_repair_is_taken_up_and_tested_before_its_resume_is_consumed_once`,
  `bash tests/factory-work-dispatch-test.sh`. Les courses réponse/retrait qui
  pourraient consommer une réponse sont tenues par
  `python3 tests/convoy-advance-resumes-stops-end-test.py ConvoyAdvanceTest.test_an_evaluation_stop_answered_while_its_request_is_cleared_is_not_resumed ConvoyAdvanceTest.test_a_removed_stage_stop_answered_while_its_request_is_cleared_is_not_resumed ConvoyAdvanceTest.test_a_grouped_answer_recorded_while_changed_parkings_are_re_raised_is_applied_first`
  et `python3 tests/convoy-advance-review-evaluation-correction-test.py ConvoyAdvanceTest.test_a_code_review_stop_answered_while_its_request_is_cleared_is_not_resumed`.
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
  se clôt sans fusion dessus).
- Ouvertes : exceptions datées du 29/10/2026, tenues une par une par le
  contrôle : `criterion_already_green` reste au Planning Run ;
  `outcome_evaluation_no_result` et `outcome_evaluation_outage` ne repartent
  qu'à une nouvelle pointe d'intégration ; `story_unobservable` reste au
  Planning Run. Elles sont retirées de la table dès qu'une transition codée
  remplace cette porte (étude B § 4.2, af-npz9v1.27).

## D — Doublure, instrument ou vue partielle qui ne se comporte pas comme le réel

- Invariant : Un faux outil refuse ce que le vrai refuse ; un instrument qui
  juge est étalonné sur un cas connu avant de servir ; on juge l'état
  résultant, jamais un morceau.
- Contrôle : `python3 tests/account-home-lint-test.py`,
  `python3 tests/fake-tool-contract-test.py`,
  `python3 tests/cockpit-isolated-https-test.py`,
  `python3 tests/evaluation-capacity-test.py`,
  `bash tests/gh-unsupported-subcommand-guard-test.sh` — complet pour le dossier
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
  tient leur suivi jetable. Le quatrième tient l'admission partagée des
  produits d'évaluation et refuse qu'une cité isolée lise les lancements, le
  verrou ou les attestations de l'usine en service ; il tient aussi le
  sous-montage des attestations en lecture seule quand leur état isolé vit
  sous le parent inscriptible `$HOME/.cache`. Le cinquième refuse dans
  `bin/` et `lib/` les formes de `gh` absentes du vrai : `gh pr
  update-branch`, et `--jq` suivi de `--arg`, que le faux `gh` de la
  relance d'un contrôle rouge acceptait (af-toyety).
- Occurrences : #566, #618, #641, #648, #656, #664, #665, #669, #671, #674,
  #675, #676, #680, #689, #690, #692, #699, #700, #714, #715 ; af-vf51g6 ;
  af-dtsy06 ; af-h6nyqc ; af-toyety.
- Ouvertes : exception datée du 29/10/2026 : la relecture de code par modèle
  n'est pas rejouée sur un cas connu (étude B § 4.3). Elle reste bornée par
  ses citations vérifiées et ses passes ciblées, mais n'est pas déclarée
  étalonnée par ce contrôle déterministe. Aucun faux `bd`/`gc` connu n'est
  hors du contrôle.

## R — Une même règle tenue à deux endroits qui divergent

- Invariant : Une règle, une fonction : un écrivain et son lecteur, ou deux
  outils, lisent la règle au même endroit.
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
  ce ticket au statut que ses portes permettent).
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
- Contrôle : `bash tests/on-order-failed-test.sh`,
  `python3 tests/factory-observe-test.py LiveObservationTest`,
  `bash tests/pr-autopilot-armed-not-merged-test.sh`,
  `bash tests/pr-autopilot-transient-retry-test.sh`,
  `python3 tests/tdd-step-test.py TddStepTest.test_green_refusal_keeps_the_failing_control_after_long_regression_output`,
  `python3 tests/role-adoption-trial-codex-test.py`,
  `python3 tests/factory-delivery-proof-test.py ClaimedShippedBead`,
  `python3 tests/ticket-graph-publish-test.py TicketGraphPublishBeadModeTest.test_a_mayor_wake_delivered_but_slow_to_answer_is_not_reported_as_lost` — partiel : le premier
  tient la frontière entre un report explicite (sortie 75, rejoué sans
  alerte) et une vraie panne répétée (bead et page Mayor) ; le deuxième tient
  la collecte VM Beads/Git/GitHub, le silence sur état inchangé, la route
  unique au plus petit propriétaire présent, la preuve durable avant l'alerte,
  sa clé stable de dédoublonnage, la conservation d'une demande humaine et le
  relevé final à +2 h ; le troisième refuse qu'une sortie locale 0 compte comme
  armement sans relecture GitHub et tient la fusion directe au head, à CLEAN et
  au contrôle requis vert ; il relit aussi GitHub après toute demande de fusion
  directe et n'annonce la fusion que si le serveur répond `MERGED`. Le contrôle
  9 du gardien (#688) couvre les tickets que personne ne bouge, pas les autres
  signaux. Le quatrième refuse qu'un workflow encore actif ou une demande de
  rerun refusée soit annoncé comme déjà retenté. Le contrôle `tdd-step`
  conserve le début et la fin d'une longue sortie bornée, dont le nom du
  contrôle en échec. Le dernier tient la minute de
  stabilité après un réveil Codex proche
  de l'échéance dans une borne fixe et exige qu'un délai dépassé nomme les états
  observés et la demande de réveil ; il refuse aussi que `active` compte comme
  provider-ready quand le premier nudge ne crée aucun rollout, et tient les
  trois dialogues interactifs (mise à jour, confiance du dossier, hooks) hors
  des profils Codex sans opérateur. Le contrôle `factory-delivery-proof` refuse
  qu'un `gc.outcome=pass` d'étape de formule (`gc.step_ref`/`gc.step_id`)
  compte comme livraison annoncée : l'étape qui ouvre la PR n'est pas une
  livraison non prouvée. Le contrôle `factory-observe` et le dernier refusent
  qu'un `gc mail send` borné, déjà remis mais lent à répondre, compte comme
  perdu : l'envoi est rejoué une fois sous la même clé `--dedup`, et seul un
  second échec est un échec.
- Occurrences : #651, #679, #688, #717 ; af-npz9v1.50 ; #767 (armement local
  annoncé mais `autoMergeRequest=null`, af-npz9v1.50.1) ; af-ncg9qy ; #778
  (demande directe acceptée localement mais encore `AWAITING_CHECKS`,
  af-nk5nm6) ; af-27yx7q.2.1 ; af-pd6m09 ; af-1l3znv (un workflow encore
  actif ou une demande de rerun refusée était annoncé comme déjà retenté) ;
  af-0rdubb ; af-eyi5wa (l'étape push-and-pr, passée en ouvrant sa PR, signalée
  comme livraison non prouvée) ; af-usvfdb (un mail d'alerte remis mais
  confirmé après le délai de 20 s comptait comme échec du gardien, et le même
  délai faisait écrire « Mayor NOT woken » à `ticket-graph-publish`).
- Ouvertes : aucune connue.

## A — Autre

- Invariant : Aucun invariant commun : une PR rangée ici dit pourquoi elle
  n'entre dans aucune autre catégorie ; trois PR de même cause font une
  catégorie nouvelle.
- Contrôle : aucun — catégorie de tri.
- Occurrences : #619, #622, #639, #655, #677 ; tests nocturnes #634, #663,
  #670, #707.
- Ouvertes : aucune connue.
