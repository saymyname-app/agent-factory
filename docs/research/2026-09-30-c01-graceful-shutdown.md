# C01 Cockpit V2 : arrêt propre et reprise de l'usine, ce que gc permet

Recherche pour le ticket wayfinder af-arlph5.14 (carte af-arlph5, « C01 —
Cockpit V2 de l'usine »). Faits seulement, aucune recommandation. Mesuré en
lecture seule le 2026-09-30 entre 13:30 et 14:30 (Paris). Aucune commande
modifiant l'état du runtime n'a été lancée : pas de stop, drain, suspend,
start, order run, POST/PATCH API, écriture bd.

Définition de « sans perte » (af-arlph5.13, validée) : aucun travail nouveau
démarré, chaque session finit son étape ou atteint un point de reprise, aucun
changement non commité perdu, beads/claims/convois identiques avant/après ;
reprise prouvée quand le premier travail repris est celui qui était en cours.

Sources :

- **Runtime live** : `gc` 1.4.1 (`/usr/local/bin/gc`, `gc <cmd> --help`),
  racine live `/home/benja/agent-factory` (HEAD `ed86548`), `.gc/events.jsonl`
  (lu par `grep -a`, jamais en entier), API GET `127.0.0.1:8372`.
- **Factory (versionné)** : `docs/RUNBOOK_STOP_AND_RESTART.md`, `city.toml`,
  `orders/*.toml`, `bin/*`, `agents/factory-worker/prompt.template.md`,
  `formulas/mol-do-work.formula.toml`.
- **UPSTREAM** : source Gas City au tag `v1.4.1` (commit `58ef17e3b`, clone
  lecture seule dans `/tmp/gascity-src-research` de
  `https://github.com/gastownhall/gascity`), dont `docs/reference/config.md`.
  Les faits marqués UPSTREAM viennent du code source, pas d'une exécution.

Glossaire minimal : **session** = un processus agent (tmux) + son *session
bead* ; **controller / reconciler** = boucle gc qui décide quelles sessions
tournent ; **drain** = demande à une session de s'arrêter ; **drain-ack** =
métadonnée `GC_DRAIN_ACK` qui fait arrêter la session au tick suivant ;
**order** = tâche planifiée exécutée par le controller.

## 1. Commandes et API : drain, suspend, stop, start

### 1.1 Inventaire

| Geste | CLI | API HTTP (8372) | Ce que ça fait (source) |
|---|---|---|---|
| Suspendre la cité | `gc suspend` | `PATCH /v0/city/{cityName}` `{"suspended":true}` | Écrit `.gc/runtime/suspension-state.json` ; le reconciler ne lance plus d'agent, `gc hook`/`gc prime` rendent vide (`gc suspend --help`). Le client CLI passe par l'API puis retombe sur l'écriture directe (UPSTREAM `cmd/gc/cmd_suspend.go:72-90`, `internal/api/client.go:1353-1364`). |
| Reprendre | `gc resume` | même PATCH `{"suspended":false}` | « explicit resumed preference », survit aux redémarrages (`gc resume --help`). |
| Arrêter la cité | `gc stop [--timeout D] [--force]` | aucune route city-stop dans `openapi.txt` | Ctrl-C à chaque session, attente `shutdown_timeout`, puis kill des survivantes ; arrête aussi Dolt ; délègue au controller s'il tourne (`gc stop --help`). |
| Démarrer | `gc start` | aucune route | Enregistre la cité auprès du superviseur et déclenche une réconciliation (`gc start --help`). |
| Redémarrer | `gc restart` | aucune route | = `gc stop` puis `gc start` (`gc restart --help`). |
| Superviseur | `gc supervisor start/stop/status` | — | Le superviseur est un service systemd utilisateur (`~/.config/systemd/user/gascity-supervisor.service.d`). |
| Suspendre un rig / un agent | `gc rig suspend <rig>`, `gc agent suspend <name>` | — | Rig : état runtime, ses agents sont sautés. Agent : `suspended=true` dans la config ; « Existing sessions continue running but won't be replaced if they exit » (`gc agent suspend --help`). |
| Session unitaire | `gc session suspend/kill/reset/wake/close <id>` | `POST /v0/city/{c}/session/{id}/suspend`, `/stop`, `/kill`, `/wake`, `/close` | suspend = arrête le processus, garde le bead ; kill = tue sans changer l'état, le reconciler relance ; reset = relance à neuf en gardant le bead (`--help` de chaque). |
| Drain d'une session | `gc runtime drain <name>` / `undrain` / `drain-check` | aucune route drain | Pose `GC_DRAIN` ; « The agent should check for drain status periodically … and finish its current task before exiting » (`gc runtime drain --help`). |
| Drain-ack | `gc runtime drain-ack` (depuis la session) | — | Pose `GC_DRAIN_ACK` et réveille le controller, qui arrête la session (`gc runtime drain-ack --help`). |
| Orders unitaires | `gc order run <name>` (pas de disable CLI) | `POST /v0/city/{c}/order/{name}/disable`, `/enable`, `/run` | Routes listées dans UPSTREAM `docs/reference/schema/openapi.txt` ; comportement de disable non exercé. |

`gc drain`, `gc stop-all` n'existent pas (`gc drain --help` affiche l'aide
générale).

### 1.2 `gc stop` n'attend pas la fin de l'étape

- UPSTREAM `cmd/gc/controller.go:972-975` : « two-pass graceful shutdown: 1.
  Send Interrupt (Ctrl-C) to all sessions 2. Wait shutdown_timeout 3. Stop
  (force-kill) any survivors ».
- `shutdown_timeout` vaut **5 s par défaut** (UPSTREAM
  `internal/config/config.go:2673-2675`, `docs/reference/config.md:324`). La
  Factory ne le règle pas : `gc config show` ne contient aucune clé
  `shutdown_timeout` (seulement `idle_timeout = "2h"`).
- `gc stop` marque d'abord chaque session active `sleep_reason=city-stop`
  (UPSTREAM `cmd/gc/cmd_stop.go:275`, `354-379`), puis, si un controller
  tourne, lui délègue l'arrêt et attend `shutdown_timeout + 15 s`
  (`cmd_stop.go:278-288`).
- Observé (Factory) le 2026-09-25 : entre 02:50:26 et 02:50:32 (Paris), les
  trois sessions s'arrêtent en ~6 s (`session.stopped` raisons « exited
  gracefully » et « stopped », seq 315494-315498) puis `city.suspended`
  (seq 315499). À ce moment la session `factory-worker` af-jyrsu avait
  l'étape `af-fayr4` (« Implement, verify, commit, and close ») assignée et
  ouverte, et la molécule `af-adwjq` (mol-do-work) `in_progress`.

### 1.3 `gc suspend` seul (controller vivant) : le seul chemin qui attend

UPSTREAM, sans exécution sur l'usine :

- Cité suspendue → l'état désiré est vide (`cmd/gc/build_desired_state.go:346-349`) :
  aucune nouvelle session.
- Pour chaque session vivante non désirée, le reconciler **saute le drain si
  la session a encore du travail assigné ouvert** : « Skipping drain for '%s':
  live assigned work found » (`cmd/gc/session_reconciler.go:2018-2041`). Il
  n'y a pas de délai dans cette branche : elle est réévaluée à chaque tick.
- Sinon il ouvre un drain de raison `suspended` avec échéance
  `defaultDrainTimeout = 5 min` (`session_reconciler.go:2070`,
  `cmd/gc/session_types.go:273`). Au tick suivant il pose lui-même
  `GC_DRAIN_ACK` (arrêt SIGTERM/SIGKILL propre, sans Ctrl-C), et à échéance il
  force l'arrêt (`cmd/gc/session_wake.go:606-647`). Un drain `suspended` n'est
  pas annulable par un réveil (`session_wake.go:207-213`).
- Pour la session nommée `mayor`, le drain attend plusieurs ticks de
  confirmation (`session_reconciler.go:2042-2069`).
- `gc hook` renvoie code 1 « city is suspended » (UPSTREAM
  `cmd/gc/cmd_hook.go:288-292`).

### 1.4 Événement `session.drain_acked_with_assigned_work`

- Définition UPSTREAM (`internal/events/events.go:62-71`) : émis quand une
  session fait drain-ack « while still holding the assignee on an open or
  in-progress work bead ». Distingue un worker sorti en pleine tâche (cap de
  tours, crash) d'un passage de relais propre (qui vide l'assignee avant le
  drain-ack). « mechanism-only signal; pack-level subscribers own the recovery
  policy ». Émetteur : `cmd/gc/session_reconciler.go:396-432`.
- Payload observé (Factory, seq 385732, 2026-09-29 16:02 Paris) :
  `session_id`, `bead_id`, `template`, `bead_status` (`open` ou
  `in_progress`), `reason`.
- Volume : 733 occurrences dans `.gc/events.jsonl` ; dernières le 2026-09-29
  (`bd.dog` avec bead `in_progress`, `factory-worker` avec bead `open`).
- Aucun order Factory n'y est abonné (`orders/*.toml` : seuls `order.failed`,
  `session.stranded`, `bead.closed`, `bead.updated` sont des déclencheurs).

## 2. Ce qu'une session interrompue perd, points de reprise

| Élément | Après arrêt | Source |
|---|---|---|
| Bead de session | Conservé, état `stopped` + `sleep_reason=city-stop` ; l'alias est retenu « we plan to resume this bead » | UPSTREAM `cmd/gc/session_beads.go:291-302`, `cmd_stop.go:354-379` |
| Même session réveillée au redémarrage | Oui le 2026-09-25 : `session.woke` af-jyrsu (factory-worker), af-jzg31 (mayor) à 14:55:40 | Factory events seq 315657, 315663 |
| Conversation du modèle | Reprise possible si le provider a un `resume_command`/`ResumeFlag` (`{{.SessionKey}}`) ; non établi pour les providers de la Factory (`gc config show` : aucune clé resume) | UPSTREAM `internal/config/config.go:3292-3294` ; non vérifié |
| Worktree non commité | Reste sur disque dans `~/.local/share/agent-factory-runtime-worktrees/<id>` ; rien ne le supprime à l'arrêt | `bin/factory-maintain:210`, `orders/clean-worktrees.toml` |
| Sauvegarde de ce non-commité | Aucune : `factory-guard` ne snapshotte que l'arbre de la racine live, les worktrees runtime sont « the city's own; leave them » | `bin/factory-guard:401-452`, `:554` |
| Worktree abandonné ensuite | `clean-worktrees` (05:00) ne supprime que fusionné ou propre/poussé > 7 j ; commits non poussés → escalade, jamais supprimé | `orders/clean-worktrees.toml` |
| Molécule mol-do-work | Étapes en beads : `workspace-setup` → `do-work` → `push-and-pr` → `drain` (drain-ack final). Chaque étape fermée est un point de reprise ; l'étape en cours n'a pas de checkpoint interne | `formulas/mol-do-work.formula.toml:112-411` |
| PR en vol | Vit sur GitHub, indépendante de gc ; `pr-autopilot` la reprend au prochain passage | `orders/pr-autopilot.toml` |
| Dolt | `dolt_stop_timeout` 30 s par défaut ; « too-short value risks SIGKILL during a journal index update » | UPSTREAM `docs/reference/config.md:325` |

Cas observé (Factory, 2026-09-25, arrêt 02:50 → reprise 14:54 Paris) :

- `af-fayr4` (étape do-work) a gardé son assignee `factory-worker-af-jyrsu` et
  a été fermée à 15:04:48 par la même session réveillée (seq 316015).
- `af-zwhh0` (ticket bug) est resté `in_progress` et s'est fermé à 15:14:53
  (seq 316327).
- La molécule racine `af-adwjq` est repassée `open` à 14:59:45, ~5 min après
  `controller.started` (seq 315761), puis fermé à 15:07:20. Un nouveau
  `mol-do-work` `af-4fpvm` est apparu à 15:00:15. L'acteur de la remise à
  `open` n'est pas identifiable : tous les événements bead portent
  `actor: cache-reconcile`, qui est le cache de lecture de gc rapportant un
  changement observé, pas l'auteur (UPSTREAM `cmd/gc/api_state.go:222-249`).

## 3. Au redémarrage : claims, beads in_progress, convois

- **Beads et convois** : stockés dans Dolt, rien dans `gc stop`/`gc start`
  ne les réécrit (UPSTREAM `cmd_stop.go:267-342` : sessions, orphelins,
  serveur, store). Le runbook Factory exige de recompter open/closed par store
  avant/après (`docs/RUNBOOK_STOP_AND_RESTART.md:34-50`, `:135-153`) ; les
  `closed` peuvent augmenter (beads `order-tracking`).
- **Réouverture par gc (core, Go)** : `releaseOrphanedPoolAssignments`
  « reopens active pool-routed work whose assignee no longer maps to any open
  session bead » (UPSTREAM `cmd/gc/pool_session_name.go:114-118`) ; ignoré si
  les snapshots sont partiels (`:95-111`). Émet `bead.dead_assignee_reopened`
  (18 occurrences Factory, dernière le 2026-09-25 01:11 Paris, seq 311831).
  Une session arrêtée par `gc stop` garde un bead **ouvert** (état
  `stopped`), donc son assignee reste « vivant » pour cette règle.
- **`session.stranded`** : émis quand une session de pool est morte avec du
  travail `in_progress` assigné (UPSTREAM `session_reconciler.go:4191-4239`) ;
  127 occurrences. L'order Factory `on-session-stranded` **rouvre chaque bead
  encore in_progress et page le Mayor** (`bin/on-session-stranded:1-13`).
- **Sweep d'orphelins** : l'order core `orphan-sweep` est désactivé
  (`city.toml:165` `skip = [..., "orphan-sweep"]`, présent dans `gc config
  show`). Le remplaçant `factory-orphan-sweep` (5 min) libère tout claim
  `in_progress` dont l'assignee n'est dans aucune session listée par `gc
  session list` ni aucun agent configuré, sauf claims `po-agent/*` et beads
  planning (`bin/factory-orphan-sweep:1-18`, `:90-150`). `gc session list`
  montre « active and suspended sessions » par défaut (`--help`) ; qu'il
  liste les sessions `stopped/city-stop` n'est pas vérifié.
- **Pool `min_active_sessions`** : le bead `city-stop` est réveillé au
  redémarrage plutôt qu'une nouvelle session créée (UPSTREAM
  `cmd/gc/compute_awake_set.go:334-343`).
- **`factory-boot`** (tâche Windows à l'ouverture de session) ne relance pas
  une cité suspendue : « SKIP city is suspended by an operator »
  (`bin/factory-boot:59-66`).

## 4. Orders pendant l'arrêt

- **Cité suspendue, controller vivant** : aucun order n'est dispatché, y
  compris exec et event (UPSTREAM `cmd/gc/order_dispatch.go:448-457`). Donc
  `factory-guard`, `pr-autopilot`, `factory-orphan-sweep`, `idle-ready-work-wake`,
  `on-session-stranded`, `on-order-failed` ne tournent pas et ne peuvent ni
  alerter ni réparer.
- **Après `gc stop`** : la cité est désenregistrée, il n'y a plus de
  controller, donc plus d'orders (`RUNBOOK_STOP_AND_RESTART.md:60-69`). Observé :
  entre `city.suspended` (seq 315499) et `city.resumed` (seq 315500), 12 h
  sans aucun événement.
- **Order par order** : `POST /v0/city/{c}/order/{name}/disable|enable`
  existe (UPSTREAM openapi) ; `city.toml [orders] skip` est l'autre mécanisme
  (lu au chargement de config). Non exercés ici.
- **Au redémarrage** : les orders à cooldown partent tous dans les premières
  minutes. Le 2026-09-25 : `controller.started` 14:55:24, puis factory-guard,
  factory-watchdog, pr-autopilot, provider-failover… entre 14:56 et 14:58 ;
  `factory-guard` a échoué « context deadline exceeded » à 14:59:40, ce qui
  a déclenché `on-order-failed` (seq 315745-315747).
- `factory-guard` signale un **rig** suspendu comme `bad` (« rig '$rig' is
  SUSPENDED — no work can be dispatched to it », `bin/factory-guard:473-479`) ;
  il n'a pas de branche pour une **cité** suspendue.

## 5. Observer l'avancement sans token

Lectures GET/CLI sans modèle, vérifiées live :

- `GET /v0/city/agent-factory/status` : `suspended`, `running`,
  `agents.running`, `work.in_progress/ready/open`, `partial`,
  `partial_errors` (live : `in_progress: 7`, `partial: true`, erreur « store
  health … context deadline exceeded »).
- `GET /v0/city/agent-factory/sessions` : `items[]` avec `id`, `state`,
  `template`, `alias`, `running`, `attached`, `last_active`.
- `GET /v0/city/agent-factory/health` : `status`, `uptime_sec`.
- `GET /v0/city/{c}/events/stream` et `/v0/events/stream` (SSE) : événements
  `session.stopped` (raison), `session.draining`, `city.suspended`,
  `session.stranded`, `session.drain_acked_with_assigned_work`.
- CLI : `gc status` (« Suspended: », agents running/stopped, « Sessions: N
  active »), `gc session list --state all`, `gc supervisor status`.
- Travail en cours : `bd list --status in_progress` par store (HQ + chaque
  rig, `bin/factory-orphan-sweep:52-88` montre qu'il faut les parcourir un par
  un).
- **Limite** : après `gc stop`, l'API 8372 ne sert plus cette cité
  (désenregistrée) ; seuls bd/Dolt et le fichier `.gc/events.jsonl` restent
  lisibles — et Dolt est lui aussi arrêté par `gc stop` (`gc stop --help`).

## 6. Arrêt forcé

| Geste | Effet | Perte possible |
|---|---|---|
| `gc stop --force` | Saute la grâce, kill immédiat (`shutdown_timeout` forcé à 0, UPSTREAM `cmd_stop.go:321-325`) | Tour en cours du modèle ; non-commité reste sur disque |
| `gc stop` (défaut) | Ctrl-C puis kill après 5 s | Idem : 5 s ne couvrent pas une étape |
| `gc session kill <id>` | Tue le processus sans toucher l'état ; le reconciler relance | Tour en cours |
| Expiration d'un drain `suspended` | `verifiedStop` après 5 min | Idem |
| `pkill`/`wsl --shutdown` sans `gc supervisor stop` | Dolt en SIGKILL | Journal Dolt à rejouer, compaction perdue (`RUNBOOK_STOP_AND_RESTART.md:74-89`) |

Dans tous les cas, les beads restent en Dolt ; un bead `in_progress` d'une
session morte déclenche `session.stranded` → `on-session-stranded` le rouvre
(réattribuable), ou `factory-orphan-sweep` le libère.

## Pièges

- **`gc stop` ≠ drain** : 5 s de grâce ; il ne lit aucun travail assigné.
- **Suspendre une cité où une session garde du travail assigné** : aucune
  échéance dans la branche « live assigned work found ». Le worker Factory, s'il
  revient à sa boucle de claim, reçoit `gc hook` code 1, affiche
  `CLAIM_REJECTED`, dort 2 s et recommence sans fin
  (`agents/factory-worker/prompt.template.md:80-108`) : il ne drain-ack pas de
  lui-même.
- **Aucun agent Factory n'appelle `gc runtime drain-check`**
  (`grep` dans `agents/`, `formulas/`) : `gc runtime drain` pose un drapeau
  que personne ne lit.
- **Tout order se tait pendant l'arrêt**, y compris les gardes ; et tout
  repart d'un coup au redémarrage (échec `factory-guard` observé).
- **Une session morte avec du `in_progress`** est rouverte par
  `on-session-stranded` : le travail peut être repris par une autre session,
  ce qui contredit « sans être réattribué ».
- **`gc stop` arrête aussi Dolt** : pendant l'arrêt, `bd` ne répond plus.
- `gc reload` ne relit pas tout (`[maintenance.dolt]` seulement au démarrage
  du controller, runbook §3).

## Non vérifié (nécessiterait d'agir)

- Comportement réel de `gc suspend` sans `gc stop` sur l'usine live : durée,
  ordre d'arrêt des sessions, sort d'une session en pleine étape.
- Que `factory-orphan-sweep` voie une session `stopped/city-stop` comme
  vivante (dépend de `gc session list --json` sur ce state).
- Que la conversation du modèle soit reprise (`--resume`) au réveil d'une
  session `city-stop` sur les providers de la Factory.
- Que `POST …/order/{name}/disable` survive à un redémarrage.
- Qui a remis `af-adwjq` à `open` le 2026-09-25 14:59:45.
