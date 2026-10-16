# Outils d'usine — ce qu'ils font, quand les lancer

> Systèmes retirés (Cockpit V1, ntfy, campagne, file/statut/preview produit,
> contrat de release, axes d'amélioration) : code et documents retirés, gardés par l'historique
> Git (non fiable, voir `decisions/PRE_REFACTOR.md`).

Trois scripts `bin/` protègent et décrivent l'usine elle-même. Ils sont **L0,
déterministes, zéro token** : aucun appel de modèle. Vous pouvez les lancer
librement.

Pour la procédure d'arrêt/redémarrage complète, voir
`RUNBOOK_STOP_AND_RESTART.md`.

---

## `./bin/factory-guard` — le garde-fou

Protège la racine vive contre les pannes qui se sont réellement produites, et
**répare seul** ce qu'il peut.

```bash
./bin/factory-guard                # par défaut : vérifie ET répare
./bin/factory-guard --check-only   # ne touche à rien, sort non-zéro si problème
./bin/factory-guard --pin <branche>  # change la branche attendue de la racine
```

Ce qu'il contrôle :

| Contrôle | Ce qu'il fait |
|---|---|
| `branch` | la racine vive est sur sa branche épinglée ; restaure si la dérive a cassé un invariant |
| `runtime-files` | `pr-autopilot`, `factory-guard` et leurs orders existent encore sur le disque |
| `exec-bits` | (af-ogg8z) chaque fichier que git suit en mode `100755` sous `bin/` est bien exécutable sur disque — restaure le bit avec `chmod +x` sinon ; `runtime-files` ne teste que l'existence (`-e`), pas l'exécutabilité, ce qui a laissé `bin/provider-failover` échouer en silence (exit 126) pendant ~2h le 2026-09-17 |
| `config-invariants` | `permission_mode` est sain et les 4 providers vérifiés (`codex`, `claude`, `claude-readonly`, `claude-standard`) résolvent |
| `work-backup` | **pousse** toute branche qui n'existe que sur cette machine |
| `work-tree` | **sauvegarde** l'arbre de travail modifié ou non suivi (voir plus bas) |
| `rig:*` | un rig suspendu bloque la livraison ; un dispatcher au repos, non |
| `build-gates` | (af-uxz57) lit, rig par rig, le catalogue de formules réellement résolu, déduplique leurs contrôles `exec`, puis vérifie que chaque chemin existe et est exécutable dans le rig concerné. Gas City refuse un lien symbolique `exec` sortant du confinement du rig : `bin/factory-build-gates` crée donc des copies régulières pour les contrôles et garde le validateur Python comme dépendance liée au pack afin qu'il résolve ses schémas voisins. Tous ces artefacts sont suivis par `.gc/scripts/.factory-build-gates.json` et actualisés depuis le pack épinglé pour ce rig ; `--check-only` nomme une seule fois chaque couple rig/chemin manquant ou périmé sans écrire. Le démarrage l'exécute avant le contrôleur, et le garde le répare ensuite après un re-clone de rig ou un re-pin du pack. La racine de la cité est réconciliée comme un magasin de plus (`(city root)`) pour les seuls contrôles que la cité possède sous `assets/scripts/` (T12 : le contrôle de la formule de l'auteur). Il ne crée jamais de faux script « toujours vrai » et refuse d'écraser un fichier propre au rig ou un artefact géré modifié hors de l'outil. |
| `worktrees` | nomme les worktrees qui épinglent encore une branche fusionnée |
| `provider overlay` | **régénère** `city.provider.toml` s'il a disparu (sans lui, la config de la cité ne charge plus) |
| `mayor-session` | (af-9ur0s) la session nommée du Mayor endormie ou en quarantaine depuis plus de 10 min est signalée directement à `${GC_ESCALATION_RECIPIENT:-human}` — elle ne peut pas lire un mail qui lui serait adressé —, une seule fois par épisode ; règle dans `lib/factory_session_boot.py` |
| `session-boot` | (af-jj9u7) vérifie qu'une session nommée toujours-active (`configured_named_mode = "always"`, ex. le Mayor) peut **démarrer** — un orchestrateur bloqué en `creating`/`failed-create` plus de 15 min (`FACTORY_SESSION_BOOT_MINUTES`) ne peut plus rien orchestrer. Le flux se lit sur `gc events` (pas de bead de coordination requis) ; `lib/factory_session_boot.py` porte les règles, y compris le suivi d'une même identité à travers plusieurs id de bead de session (l'incident réel a alterné `creating`/`failed-create` sur des dizaines de beads). Le signalement nomme la session, son fournisseur/commande et le dernier `state_reason`/`close_reason`, et est envoyé directement à `${GC_ESCALATION_RECIPIENT:-human}` — jamais au Mayor, qui peut être précisément la session bloquée |

**La sauvegarde de l'arbre de travail** mérite une explication. Un fichier que
`.gitignore` couvre est hors périmètre par déclaration du dépôt. Tout le reste
— modifié ou jamais suivi — est, par définition, quelque chose que ce dépôt a
l'intention de suivre. Le garde ne peut pas committer à votre place : il tourne
sans surveillance sur une racine dont le `HEAD` et l'index appartiennent à qui y
travaille. Il prend donc un **instantané qui ne touche à rien** — index jetable,
`write-tree`, `commit-tree` sur `HEAD` — poussé vers
`refs/factory-guard/snapshots/<utc>`, dont il conserve les dix plus récents.

Un instantané contient des fichiers non commités et des commits que personne
n'a relus : il n'a rien à faire sur un dépôt lisible par des inconnus. Quand le
dépôt nomme un remote `backup` (un dépôt privé), les instantanés et les
sauvegardes de worktrees y vont ; sans lui, ils vont vers `origin`
(af-996mmd). Sur cet hôte, le `backup` de la racine est le dépôt privé
`saymyname-app/agent-factory-archive` : `git remote get-url backup`.

Pour récupérer un instantané (`origin` à la place de `backup` pour un dépôt
sans ce remote) :

```bash
git fetch backup 'refs/factory-guard/snapshots/*:refs/remotes/snapshots/*'
git log --oneline refs/remotes/snapshots/*        # lister
git show refs/remotes/snapshots/<utc>:<fichier>   # lire un fichier
```

**Budget de temps** (2026-09-29). L'order tue le garde à 180 s ; un passage
normal prend ~30-45 s. Le 2026-09-28 à 14:09, l'hôte Windows saturé a étiré
des appels `gh`/`git`/`gc` sans borne au-delà de 180 s : le garde a été tué
sans aucun rapport. Désormais chaque appel réseau, Dolt ou sous-garde passe
par `bounded` (plafond propre : `gc` 15-30 s, `git` réseau 30 s, `gh` 20 s,
sous-gardes 60 s, jamais au-delà de budget + 20 s) ; un appel coupé vaut
« inconnu » — jamais vert, jamais une raison d'agir (un `gh pr list` coupé
ne supprime pas de worktree). Aucune section ne démarre après 150 s
(`FACTORY_GUARD_BUDGET_SECONDS`) : chaque section sautée sort en problème
« not checked (time budget exhausted) » et le garde rend son rapport. Un
passage lent (> 60 s, `FACTORY_GUARD_SLOW_SECONDS`), écourté ou avec un appel
coupé imprime, même en `--quiet`, la durée de chaque section et
`/proc/loadavg` : charge élevée et toutes les sections plus lentes = hôte
saturé ; une seule section et une ligne `timed out:` = un appel bloqué.

**Quand le lancer** : avant tout arrêt, après toute session qui a touché la
racine, et avant de croire qu'un travail est en sécurité. Il tourne aussi seul
via son order.

*Pourquoi il existe* : le 2026-09-15 un `git checkout` dans la racine vive a
mis le merge actor hors ligne et fait retomber `permission_mode` sur `plan`,
qui bloque les agents non surveillés. Rien ne l'a signalé pendant vingt minutes.
Le 2026-09-16, le contrôle `work-backup` affichait « nothing exists only on this
machine » alors que vingt entrées, dont deux ADR acceptés, n'existaient que là.

---

## `./bin/factory-watchdog` — la surveillance qui page, pas seulement qui observe

Plusieurs signaux peuvent rester muets sans que rien ne casse visiblement
(incident du 2026-09-16, `git show 987d497:legacy/docs/INCIDENT_2026-09-16-silent-campaign-stall.md`, af-539b0) :

```bash
./bin/factory-watchdog                # par défaut : vérifie ET page (mail + bead)
./bin/factory-watchdog --check-only   # ne touche à rien, sort non-zéro si problème
```

| Contrôle | Ce qu'il fait |
|---|---|
| `gates` | une « Gate: human » ouverte depuis plus de 30 min (réglable) est re-signalée au Mayor, pas seulement laissée dans la file — sauf si l'attente est déjà une demande active dans la liste de l'opérateur (`gc.needs_benjamin` sur le bead que la porte bloque, ou sur le convoi qui le suit) : elle est alors affichée, jamais paginée (af-brjmv6) |
| `prs` | une PR du dépôt Factory en `CONFLICTING`, ou dont aucun contrôle CI n'a jamais démarré, après 30 min — distincte d'une PR qui attend simplement son tour |
| `workflows` | un bead molécule/workflow fermé `CLOSED` avec `gc.outcome` ≠ `pass` (le cas `on_fail=abort_scope` : chaque étape en aval passe `outcome=skipped` en silence) — sauf le workflow d'une formule du nouveau flux, nommée dans `config/delivery-flow.json` : son résultat est lu par `bin/convoy-advance`, qui reprend, relance ou arrête le ticket lui-même (af-yzo8fo.2) |
| `gh-auth` | `gh auth status` échoue (token WSL périmé/invalide) — neuf scripts en dépendent (`reversibility-check`, `factory-guard`, `pr-autopilot`, `factory-do-work-workspace`, `factory-gh-rollup`, `factory-delivery-guard`, `deliver-close`, `factory-watchdog`, `factory-main-gate`) et échouaient chacun silencieusement de son côté (af-539b0, 2026-09-18) ; **un seul** bead partagé nommant les neuf scripts, **un seul** mail au Mayor par cooldown, et auto-résolu dès que `gh auth` revient — jamais un bead par script, jamais un par passage |

**Observe et page seulement** (ADR-0016 §7) : il ne résout jamais une porte,
ne fusionne ni ne ferme jamais une PR, et ne rouvre jamais un workflow. Chaque
signalement devient au plus un mail au Mayor (`gc mail send mayor --notify`,
relancé sur un délai de repli, jamais à chaque passage) et, pour les portes et
PR, un bead qui survit au passage suivant. Les règles pures sont dans
`lib/factory_watchdog.py`.

Les signalements n'écrivent plus dans un fichier signal local : depuis le
retrait du Cockpit V1 rien ne lisait `.gc/runtime/factory-watchdog-signals.json`,
et O06 (Factory operations v2) a retiré cet écrivain (`factory-watchdog`,
`on-order-failed`, `on-session-stranded`) ainsi que
`lib/factory_watchdog.py`'s `merge_signals`.

**Quand le lancer** : il tourne seul via son order (`orders/factory-watchdog.toml`,
5 min, bien en-dessous de l'heure qui a coûté 4h20 le 2026-09-16-17).

---

## `./bin/mayor-context-guard` — la conversation du Mayor a-t-elle trop grossi ?

Filet de la règle « Handoff » du prompt du Mayor (af-3ewcxf : une conversation
a atteint 365k tokens). L0, zéro token, lancé par `orders/mayor-context-guard.toml`
toutes les 10 min.

```bash
./bin/mayor-context-guard --check   # une ligne JSON : la décision, sans rien toucher
```

Il lit la session `mayor` (`gc session list --json`, champ `session_key` = id
de conversation Claude), puis son transcript
`~/.claude/projects/<work_dir>/<session_key>.jsonl` : tokens de contexte = usage
du dernier message assistant (`input` + `cache_read` + `cache_creation`), âge =
premier horodatage. Au-delà de **150k tokens** (`MAYOR_CONTEXT_GUARD_TOKENS`) ou
**8 h** (`MAYOR_CONTEXT_GUARD_MAX_AGE_HOURS`), et seulement entre deux tours
(dernier `stop_reason` = `end_turn`) et sans personne attaché, il lance
`gc session reset mayor` (conversation neuve, même bead, alias et courrier) puis
envoie au Mayor un mail `HANDOFF:` (champs OPEN_MAIL/OPEN_DECISIONS/IN_FLIGHT/NEXT
marqués inconnus). Un reset en échec n'est pas enregistré et sort en 1 (l'ordre
échoue, la passe suivante réessaie).
Une seule rotation par conversation (`.gc/runtime/mayor-context-guard-state.json`),
journal dans `var/mayor-context-guard.log`, jamais une autre session.

Pourquoi pas `gc handoff --target mayor` ni `max_session_age` : tous deux
redémarrent la session selon son `wake_mode`, et le Mayor a celui par défaut
(`resume`) — il reprendrait la même conversation trop longue. `gc session reset`
est la primitive documentée de redémarrage à neuf.

---
## `./bin/factory-metrics` — les chiffres d'une journée de l'usine

Une ligne JSON par jour dans `var/factory-metrics.jsonl` (af-lw581v). L0, zéro
token, lancé chaque nuit à 00:30 par `orders/factory-metrics.toml` pour la
veille (jour calendaire local). Lecture seule partout ailleurs.

```bash
./bin/factory-metrics --print                  # hier, sur la sortie seulement, sans rien ajouter
./bin/factory-metrics --day 2026-10-14 --print # un jour donné
```

| Champ | Source |
|---|---|
| `tickets_merged`, `merged_tickets` | tickets dont `gc.flow.merge` vaut `merged` avec un `at` dans la journée (`gc bd list`, magasin HQ) |
| `attempts_per_ticket`, `attempts_mean` | 1 + `gc.flow.counter.resumes` de chaque ticket fusionné (les rondes de correction y sont comptées) |
| `tokens_total` | usage (entrée, sortie, cache lu et créé) des messages assistant de la journée, dédoublonnés par id, dans `~/.claude/projects/*/*.jsonl` — **toutes** les sessions, pas seulement le travail des tickets |
| `tokens_per_merged_ticket` | `tokens_total / tickets_merged` : un ratio de la journée, pas une attribution par ticket |
| `order_runs`, `order_failure_rate` | événements `order.completed` / `order.failed` de la journée dans `.gc/events.jsonl` ; taux = échecs / (réussites + échecs), par ordre et au total |
| `sessions_over_150k` | transcripts dont le plus grand contexte d'un tour de la journée (entrée + cache lu + cache créé) dépasse 150 000 |
| `evaluation_duration_seconds` | toujours `null` : une ronde de `gc.flow.evaluation` ne garde que sa fin (`at`), la demande qui portait le début est effacée à l'enregistrement |

Un champ dont la source manque (ou qui n'a pas de sens ce jour-là, par exemple
aucun ticket fusionné) vaut `null` et figure dans `unavailable`, sa cause dans
`unavailable_reasons` — jamais un zéro inventé.

---
## `./bin/factory-resources` — la capacité de l'hôte

Répond à « l'usine a-t-elle de quoi travailler, et laisse-t-elle vivre
Windows ? ».

```bash
./bin/factory-resources
```

Il lit la mémoire et le swap du guest, le plafond CPU déclaré dans
`%USERPROFILE%\.wslconfig`, et les plus gros consommateurs de mémoire.

**Quand le lancer** : quand la machine rame, avant d'augmenter la concurrence
des agents, et après toute modification de `.wslconfig`. C'est lui qui prouve
qu'un plafond a bien été pris en compte.

Les plafonds actuels et leur justification sont dans
`RUNBOOK_STOP_AND_RESTART.md` §7. Modifier `.wslconfig` exige un
`wsl --shutdown` pour prendre effet.

---

## Oracle public d'une City fixture

`./bin/fixture-city-oracle run <scenario> --operator <adapter>
--publication-door <adapter>` exerce un intent synthétique uniquement par les
surfaces publiques de l'opérateur et de la porte de publication. Il recalcule
les digests, vérifie les Work Planes positifs, le convoy, les arêtes, les
révisions Git réellement assemblées, leur compatibilité publique et la
distinction Delivered/Accepted. Les adapters sont confinés par Bubblewrap sans
réseau ni accès au domicile hôte. Une injection `after-stage` doit laisser zéro
graphe, bead delivery ou convoy. Le résultat JSON est déterministe et ne dépend
pas du Cockpit V1. Contrat complet : `FIXTURE_CITY_ORACLE.md`.

`./bin/fixture-city-oracle run <scenario> --delivery-driver <driver>` fait
parcourir le flux de livraison à un ticket d'un convoi marqué et observe son
état public après chaque événement : publié, démarré, rouge, gel, code,
revue, évaluation, fusion, fermé par la porte de fin de ticket. Un ticket
fermé hors porte fait échouer l'oracle.

Pendant ce parcours l'oracle enregistre lui-même les commandes du flux
exécutées : le driver les lance depuis le répertoire reçu dans
`FIXTURE_CITY_FLOW_BIN`, rien de ce qu'il déclare n'est utilisé. Chaque état
de l'étape d'auteur (rouge, gel, vert, Handoff, terminé) doit avoir été
écrit par sa porte (`tdd-step`, `ticket-exit exit`) ; un état écrit hors de sa porte, ou un ticket
fermé sans être passé par les portes de l'auteur, fait échouer l'oracle
(T37). Le résultat nomme les commandes vues (`interfaces.flow`) et le nombre
de tickets passés par toutes les portes (`author_gates`).

Avec `expect.outcome: "delivered"` et `expect.repairs` (T26), le parcours
continue jusqu'à la fin de Spec : l'oracle compte les tickets de réparation
publiés par le flux, fait parcourir chacun jusqu'à la porte de fin de ticket,
puis exige Delivered enregistré sur la pointe de la branche d'intégration,
`bin/spec-end check` vert, un compteur de tours de fin égal au nombre de
réparations, aucun arrêt et aucune demande sur la liste de l'opérateur. Il
échoue si Delivered est vu alors qu'une condition manque.
## `./bin/factory-doctor` — « y a-t-il quelque chose que je puisse réparer ? »

`gc doctor` rapporte sur toute la pile, la nôtre **et ses dépendances**. Ce
script relit sa sortie JSON et trie chaque problème par son **origine réelle**,
pour que le signal ne se noie pas dans ce qui ne nous appartient pas.

```bash
./bin/factory-doctor          # seulement ce qui est actionnable ici
./bin/factory-doctor --all    # détaille aussi ce qui est écarté, et pourquoi
./bin/factory-doctor --json
```

Quatre verdicts, **tous redérivés des preuves à chaque exécution** :

| Verdict | Signification |
|---|---|
| `ACTIONABLE` | problème bloquant dont les preuves sont dans ce dépôt — **le seul qui fait sortir en non-zéro** |
| `DID NOT ANSWER` | le contrôle a expiré. Il n'a pas échoué : il n'a pas répondu. Toujours affiché, jamais compté comme une panne. À poursuivre **seulement s'il persiste** |
| `UPSTREAM` | bloquant, mais tous les chemins cités sont dans le cache de packs : pas réparable d'ici |
| `ADVISORY` | la sévérité consultative de `gc doctor` — auto-résolutif ou attendu |

**Rien n'est masqué par son nom, et il n'y a aucune liste d'exceptions à
entretenir** — c'est précisément ce genre de liste qui se périme et rend
aveugle. Si l'amont corrige un jour ses formules, le warning cesse simplement
d'apparaître ; s'il se met à citer un fichier de ce dépôt, il repasse
`ACTIONABLE` tout seul, sans que personne n'édite quoi que ce soit.

Comme seul `ACTIONABLE` sort en non-zéro, ce script est sûr à câbler dans un
contrôle automatique.

### Pourquoi il existe : les 34 warnings de formules

Enquête du 2026-09-16, faite une fois pour ne plus jamais être refaite :

- Les **34** warnings `formula-requirements` sont **une seule et même cause** :
  `contract = "graph.v2"`, déprécié.
- **Aucun n'est dans ce dépôt.** Tous sont dans les formules du pack `gascity`,
  en lecture seule sous `~/.gc/cache/repos/`.
- **Mettre le pack à jour n'y changerait rien** : la branche `main` de
  `gastownhall/gascity-packs` porte encore la forme dépréciée, 88 occurrences,
  et notre copie épinglée en est identique.
- `daemon.formula_v2` est **déjà** à `true` de notre côté. Rien n'est cassé.

Il n'y a donc rien à corriger ici, et rien à attendre d'une mise à jour. Le seul
levier restant est de le signaler à l'amont. En attendant, le tri les écarte
pour qu'ils cessent de coûter une enquête à chaque session.

### `order-firing-current` intermittent : bruit de bord, pas une panne

Mesuré le 2026-09-16 : `gc doctor --json` prend 19 à 26s par exécution ici
(jusqu'à 105s sous 6 `gc order check` concurrents), et `order-firing-current`
lit « last fired » à la minute près. Pour un ordre au rythme d'1 minute, ce
budget est plus petit que le temps de scan du contrôle lui-même — un ordre
parfaitement sain peut se faire lire à « 1m depuis le dernier tir, attendu
toutes les 1m » et déclencher `(overdue)` par pur effet de bord, avant de
redevenir propre au cycle suivant.

Douze exécutions de `gc doctor --json` coup sur coup contre l'usine réelle :
9 en warning, 3 propres. Dans les 9, **chaque** ordre signalé `(overdue)`
avait un intervalle attendu d'1 minute (`dolt-health`, `beads-health`,
`gate-sweep`, `order-tracking-sweep`, `mayor-campaign`), jamais deux fois le
même ordre d'affilée, et jamais plus de 2× son propre budget (le pire :
« 2m depuis, attendu 1m »). Aucun ordre à intervalle plus long n'a jamais été
signalé — pas même ceux frôlant leur échéance (`jsonl-export` à « 14m/15m »
propre à un tir, « 15m/15m » propre au suivant). Un vrai ordre bloqué
s'annonce par un grand multiple de son propre intervalle, pas un frôlement
d'un cycle (`mol-dog-backup` à 273min sur un budget de 360min/6h n'est
jamais signalé).

`bin/factory-doctor` reclasse donc ce cas précis en `DID NOT ANSWER` :
seulement quand tous les ordres marqués `(overdue)` ont un intervalle attendu
≤ 2 minutes et sont à moins de 2,5× ce budget — sinon (intervalle plus long,
ou dépassement massif), le contrôle reste `ACTIONABLE`. Voir
`order_firing_is_boundary_noise()` dans `bin/factory-doctor` et les tests
associés dans `tests/factory-doctor-test.py`.

## `./bin/provider-failover` — quel modèle fait tourner l'usine

Quand un quota GPT ou Claude est atteint, l'usine **bascule seule** sur le
fournisseur suivant, et **revient seule** quand le quota se réinitialise. Plus
personne n'a à éditer `city.toml` ni à se souvenir de « revenir à Codex ».
Détails et règles : `decisions/ADR-0018-automatic-provider-failover.md`.

**Réglages manuels** (réversibles, zéro token) :

```bash
./bin/provider-failover status                    # qui tourne sur quoi, et pourquoi
./bin/provider-failover tick --dry-run            # ce que ferait le prochain passage
./bin/provider-failover set --action mark --by <qui> \
    --args '{"pool":"anthropic","until":"2026-09-16T16:50:00Z"}'
./bin/provider-failover set --action clear --by <qui> --args '{"pool":"anthropic"}'
./bin/provider-failover apply                     # régénère city.provider.toml
```

Trois fichiers, un seul écrivain :

| Fichier | Rôle | Versionné |
|---|---|---|
| `config/provider-policy.json` | pools, fournisseurs, chaîne de repli par cible | oui |
| `.gc/provider-state.json` | limites détectées, réglages manuels, historique | non |
| `city.provider.toml` | surcouche **générée**, incluse par `city.toml` | non |

**Ne jamais éditer `city.provider.toml` à la main**, ni le fournisseur dans
`city.toml` (ce n'est plus qu'une valeur de secours). **Ne jamais supprimer**
`city.provider.toml` : sans lui la config ne charge plus — le garde-fou le
régénère, mais autant ne pas lui en donner l'occasion.

Un quota s'applique à un **pool** : les trois profils Claude partagent le même
compte, donc une limite Claude les épuise tous. Codex standard est son propre
pool.

Si **aucun** fournisseur ne reste pour aucun pool (épuisement total, O08,
af-harft), `bin/dispatch-door` (et donc `bin/factory-work-dispatch`) refuse
tout nouveau dispatch avec une raison explicite tant que
`./bin/provider-failover status --json` lit `total_exhaustion.active`. Le
`tick` périodique dépose alors **une seule** ligne NEEDS BENJAMIN (un bead
dédié, via `escalation-door benjamin`) ; dès qu'un fournisseur redevient
disponible, le même `tick` referme ce bead et efface l'état tout seul — le
dispatch reprend au prochain appel sans intervention humaine.

La tâche planifiée `provider-failover` tourne toutes les 2 min (~1 s, < 1 s de
CPU : les écrans sont lus via tmux, pas via `gc session peek` qui coûtait 8 s).

### L'ouvrier du dépôt Factory

Pour une modification ordinaire du dépôt `agent-factory`, le Mayor lance :

```bash
./bin/factory-work-dispatch af-xxxxx
```

Cette porte choisit elle-même `factory-worker`, `mol-do-work` et
`--reassign`. Elle ne propose volontairement aucun choix de cible :
`workspace` est la **classe de fournisseur** pilotée par le repli automatique,
pas un agent Gas City, et `bd.dog` ne fait que la maintenance Dolt. L'ouvrier
Factory ne fixe aucun fournisseur dans son `agent.toml`; il prend donc celui
que `provider-failover` a résolu pour `workspace` (Codex aujourd'hui, puis le
repli configuré si nécessaire).

Une seule session `factory-worker` peut être active. Son protocole réclame
chaque étape avec `gc hook --claim --json`, puis réclame immédiatement la
suite du même groupe avant de se drainer. Ainsi le worktree, l'implémentation
et l'ouverture de PR restent dans la même session logique; une cible de
maintenance ne peut plus être sélectionnée par cette porte. Le bead de travail
reste `in_progress` mais sans assignee entre les étapes : sinon le hook le
reprendrait avant l'étape suivante du graphe. Pour annuler ce
choix, revenir sur le rôle, la porte et leur documentation : la politique de
fournisseurs reste indépendante.

---

## `./bin/pr-autopilot` — fusion et réveil de livraison

Toutes les trois minutes, ce robot sans modèle arme les PR éligibles, puis
recopie la preuve des PR fusionnées sur leur bead (`merge_result`, SHA, numéro
et branche cible). Un rattrapage historique reste volontairement silencieux :
le Mayor n'est réveillé que si un bead encore `open`/`in_progress` attend
réellement ce travail (`blocks` ou `gc.waiting_on`) ; une fusion que rien
n'attend, même récente, ne le réveille plus (af-yzo8fo.3 : 8 réveils en 42
heures répondus « rien à avancer »). Le message unique part de l'identité
explicite `pr-autopilot`, jamais de `human`; un passage ultérieur voit
`merge_result` et ne le renvoie pas.

Ainsi, le rattrapage complète les preuves sans réveiller le Mayor pour des
fusions anciennes, tandis qu'une livraison récente ou bloquante réveille le
Mayor immédiatement.

Le robot ne touche qu'aux PR ouvertes depuis une branche du dépôt lui-même par
un des comptes GitHub de l'opérateur (`config/operator.toml`,
`github_logins`). La PR d'un fork ou d'un autre auteur est laissée à un
humain : ni armée, ni fusionnée, ni relancée, ni étiquetée, ni transformée en
bead. Liste vide : rien n'est armé et le passage compte une erreur
(af-996mmd, `docs/DELIVERY.md`, « Outside authors are left to a human »).

---

## `./bin/reversibility-check` — ce changement peut-il être défait ?

Classe chaque nouvelle migration Flyway d'un diff (perte de schéma, perte de
données, réécriture, renommage) et vérifie qu'elle porte la déclaration
attendue. Le robot de fusion (`pr-autopilot`) l'exécute sur chaque PR ouverte et
retient ce qui ne peut pas être défait. Règle complète et gestes du rédacteur :
`DELIVERY.md` › *Réversibilité par défaut* ; décision : ADR-0019.

```bash
./bin/reversibility-check --git rigs/saymyname-backend --base origin/dev   # avant d'ouvrir une PR
./bin/reversibility-check --pr 57 --repo saymyname-app/Say-my-name-back    # une PR ouverte
./bin/reversibility-check --pr 57 --repo … --comment                        # le commentaire en français
```

Sortie : `0` réversible · `3` déclaration requise · `4` déclaré irréversible
(escalade) · `2` impossible de vérifier.

---

## `gc doctor` — la santé de la cité

```bash
gc doctor              # rapport
gc doctor --fix        # répare ce qui est réparable seul (hooks, liens)
```

Lisez les `✗` avant les `⚠`. Plusieurs warnings sont **consultatifs et
s'auto-résolvent** — la rétention `order-tracking` est purgée par un watchdog,
et un rig sur une branche de feature est normal pendant qu'il travaille.

**N'appliquez pas** le hint `rig:*:root-branch` qui suggère
`git checkout dev` : ces rigs sont des racines vives avec du travail en cours.
## `./bin/role-adoption-trial` — un rôle de livraison reçoit-il bien ses skills, et rien d'autre ?

L'usine a trois rôles de livraison (`config/delivery-roles.json`, Spec
af-wf4w5r §1) :

| Rôle | Agent | Skills de Matt reçus | Lecture seule |
|---|---|---|---|
| auteur | `delivery-author` | `tdd`, `codebase-design` (lit `implement`) | non |
| relecteur | `delivery-reviewer` | `code-review`, seul skill de revue qu'il peut lancer | oui |
| Evaluator | `delivery-evaluator` | aucun | oui |

Ce qu'une session reçoit vraiment dépend de Gas City et du CLI du
fournisseur : cela ne se lit pas dans un fichier, cela s'essaie. `run` monte
une **cité isolée** (son propre `GC_HOME`, son port de superviseur, jamais la
cité live), ouvre une session réelle par rôle et par fournisseur déclaré, et
relève : les skills chargés (lus dans le transcript de la session), l'empreinte
du `code-review` chargé par le relecteur, le résultat d'une demande de lancer
`code-review`, `security-review` et `review` faite à chaque rôle, et le résultat
d'une demande d'écrire, de committer et de pousser faite à un rôle en lecture
seule.

Règle des skills de revue (user story 75, T47) : le relecteur lance son
`code-review` et rien d'autre ; l'auteur et l'Evaluator n'en lancent aucun. Un
skill de revue listé ou lancé en plus fait échouer l'essai. Deux réglages
tiennent cette règle chez les trois rôles : `CLAUDE_CODE_DISABLE_BUNDLED_SKILLS=1`
(`agents/<agent>/agent.toml`) retire les skills intégrés à Claude Code, dont
`security-review` ; `syncClaudeAiPlugins` et `syncClaudeAiSkills` à `false`
(`agents/<agent>/overlay/.claude/settings.local.json`) retirent les plugins et
skills du compte claude.ai, dont un autre `code-review`.

```bash
./bin/role-adoption-trial status                # chaque rôle × fournisseur déclaré : essai valide ou non
./bin/role-adoption-trial run                   # essai réel (~1 min par rôle, consomme du quota), écrit le relevé
./bin/role-adoption-trial run --role reviewer   # un seul rôle
./bin/role-adoption-trial verify-distribution   # les copies par rôle = la distribution, octet pour octet
```

- **Relevé** : `config/role-adoption-trials.json`, versionné. Il se committe par
  PR depuis un worktree ; ne jamais l'éditer à la main, relancer l'essai.
- **`check`** (lu par `bin/dispatch-door --role`) ne se fie pas au seul
  `passed` du relevé : il relit les lancements relevés et refuse, en nommant le
  skill, un relevé où un skill de revue hors du rôle s'est lancé, où le
  `code-review` du relecteur ne s'est pas lancé, ou qui ne dit pas ce qui s'est
  lancé.
- **Empreinte** : un essai vaut pour un rôle, un fournisseur et une empreinte
  (entrée du rôle, tous les fichiers de `agents/<agent>/`, profil du fournisseur
  dans `city.toml`, `bin/delivery-role-sandbox`). Changer l'un d'eux annule
  l'essai : `tests/dispatch-door-role-test.sh` passe au rouge et
  `bin/dispatch-door --role <rôle>` refuse, jusqu'au nouvel essai.
- **Fournisseurs déclarés** d'un rôle : la chaîne de la cible de son agent dans
  `config/provider-policy.json`. N'y ajouter un fournisseur qu'avec son essai.
  Seul Claude Code est observable aujourd'hui (aucun observateur pour Codex :
  un essai sur Codex échoue, donc la porte tient le rôle hors de Codex).
- **Lecture seule** : le relecteur et l'Evaluator tournent sur un profil
  `*-readonly`, lancé par `bin/delivery-role-sandbox` (Bubblewrap : tout en
  lecture seule sauf le répertoire de travail de la session, l'état du
  fournisseur, `.gc/` et `.beads/` ; aucun identifiant de push).
- **Dossier de l'essai** : `~/.local/share/af-role-trial` par défaut, effacé à
  chaque essai. Le garder court (chemins de sockets) et stable : Claude Code
  refuse de démarrer sans surveillance dans un dossier jamais approuvé.

Sortie de `run` et `status` : `0` tout est réussi · `1` au moins un échec ·
`2` l'essai n'a pas pu être mené.

---

## `./bin/convoy-advance` — qui démarre les tickets d'un convoi du nouveau flux ?

Du code, pas le Mayor (Spec af-wf4w5r §0 règle 3, T04). Pour un convoi qui
porte la **marque du nouveau flux** (`docs/CONVOY_STATE.md`), une passe démarre
chaque ticket ouvert, jamais démarré, dont tous les bloqueurs sont fermés, tant
qu'il reste une place sous le plafond N. Chaque démarrage passe par
`bin/dispatch-door --convoy`, qui l'enregistre. Un convoi sans marque n'est pas
touché : il reste avancé par le Mayor.

```bash
./bin/convoy-advance --all          # une passe sur tous les convois marqués ouverts
./bin/convoy-advance <convoi>       # une passe sur un convoi
./bin/convoy-advance --check-only   # sortie 0 s'il existe un convoi marqué ouvert
```

- **Personne ne la lance à la main** : l'ordre `orders/convoy-advance.toml` la
  lance à chaque tick du contrôleur (toutes les 20 à 30 secondes), seulement
  s'il existe un convoi marqué ouvert.
- **Plafond N** : `max_sessions` dans `config/delivery-flow.json`, le plafond
  des auteurs, un seul réglage pour toute l'usine, partagé entre les Specs.
  Comptent : chaque session vivante d'auteur et chaque ticket démarré
  qu'aucune session n'a encore pris. Le relecteur et l'Evaluator ont leurs
  propres plafonds (`max_reviewer_sessions`, `max_evaluator_sessions`,
  appliqués par Gas City) et ne prennent pas la place d'un auteur (af-4xxlo7).
- **Formule de démarrage** : `start.formula` dans le même fichier, aujourd'hui
  `mol-ticket-author` (la formule de l'auteur, `docs/TICKET_AUTHOR.md`). À
  `null`, la commande refuse de démarrer quoi que ce soit (sortie 1).
- **Formule de reprise** : `resume.formula` dans le même fichier, aujourd'hui
  `mol-ticket-resume`. Sans ce réglage, un ticket à reprendre est refusé par
  la passe, nommé sous `refused` (sortie 1).
- **Sorties** : 0 passe faite ; 1 refus (réglage, tracker, porte de dispatch
  qui refuse un ticket ou une reprise, nommé sous `refused`, incident ou
  demande groupée impossible à lever) ;
  3 « état sans règle » : rien n'est démarré dans ce convoi ; 4 « pas un convoi
  du nouveau flux ».
- **Ticket arrêté pour amendement épuisé** : au second amendement d'un test
  gelé, `./bin/tdd-step amend` arrête le ticket ; la passe suivante pose
  **une seule** demande, « Ticket <id> arrêté : amendement épuisé — … », dans
  `./bin/escalation-door list`. Le ticket n'est ni repris ni fusionné, les
  tickets qui ne l'attendent pas continuent. Rien ne lève encore cet arrêt.
- **Convoi arrêté (« état sans règle »)** : un ticket démarré ou fermé hors de
  sa porte, une preuve sans empreinte, un compteur incohérent. La passe ne
  démarre plus rien dans ce convoi et lève **un seul** incident d'usine : la
  ligne « Incident d'usine : <ticket> — <raison> » apparaît dans
  `./bin/escalation-door list`. Réparer, c'est remettre le tracker dans un état
  valide (`./bin/convoy-state show <convoi>` dit ce qui cloche), **jamais**
  avancer ou fermer un ticket à la main. Dès que l'état est valide, la passe
  suivante reprend le convoi, retire l'incident et ferme son bead toute seule.
- **Revue de code avant la fusion** : la même passe envoie le diff de chaque
  ticket terminé et vert à une session du rôle relecteur
  (`./bin/code-review settle`), relance une fois une revue restée sans
  résultat, puis arrête le ticket et le fait remonter dans
  `./bin/escalation-door list`. Rien ne fusionne sans verdict favorable.
- **Évaluation sur le produit lancé avant la fusion** : la même passe lance
  le produit de chaque ticket terminé et vert depuis une copie propre de sa
  branche et l'envoie à une session du rôle Evaluator
  (`./bin/ticket-evaluation settle`) ; pour un `prefactoring`, elle vérifie
  elle-même que le produit démarre. Les produits lancés restent debout
  entre deux passes et sont arrêtés par une passe suivante.
- **Un seul tour de correction, puis l'arrêt** : quand la revue et
  l'évaluation ont toutes deux répondu et que l'une refuse, la même passe
  envoie tous leurs constats à une seule session neuve d'auteur
  (`./bin/correction-round settle`). Encore refusé après ce tour, le ticket
  est arrêté sans fusionner et remonte une fois dans
  `./bin/escalation-door list`.
- **Fermeture par la porte de fin de ticket** : la passe qui fusionne un
  ticket le ferme si ses neuf conditions sont réunies
  (`./bin/ticket-end settle`) ; avant la fusion, elle mesure la fidélité
  d'un ticket d'interface (`./bin/ticket-end fidelity`). Un ticket laissé
  ouvert est listé avec la condition qui manque.
- **Reprises comptées, parcage à la troisième** (T20) : à chaque passe, un
  ticket dont l'auteur doit le reprendre part vers **une** session neuve
  d'auteur, sur la même branche, sur un bead « Reprise — <ticket> ». Causes :
  `interrupted` (sortie « interrompu », ou session terminée sans sortie),
  `returned` (la fusion a rendu le ticket : conflit ou rouge), `unblocked`
  (son `repair` est fermé), `answered` (la demande qui le parquait a sa
  réponse), `behind` (terminé sur une branche qui ne contient pas la pointe
  de la branche d'intégration : `bin/code-review` n'y envoie aucun
  relecteur, T44). Chaque reprise est comptée et prend une place sous N. À la
  troisième d'une même cause (`bounds.resumes`, une borne par cause :
  celles-ci et un commit après verdict ; le tour de correction garde sa
  propre borne d'un tour, ADR-0030 L2), le ticket est parqué avec ceux qui
  l'attendent et n'est pas relancé ; les autres continuent. Listes `resumed`, `parked`,
  `lifted` dans la réponse.
- **Une seule demande groupée** (T20) : quand il ne reste dans un convoi que
  des tickets parqués, la passe lève **une** ligne pour le convoi dans
  `./bin/escalation-door list`, sur un bead « Demande groupée : convoi … »
  qui nomme chaque ticket parqué et sa cause — jamais une par ticket. Répondre `a`
  relance les tickets aux reprises épuisées (trois reprises de nouveau) ;
  `b` les laisse parqués, la demande ne revient pas.
- **Lever un parcage, c'est répondre** : `./bin/escalation-door repondre` sur
  la demande du ticket (demande opérateur : toute réponse ; Planning
  Exception : seulement l'option qui accepte l'écart) ou sur la demande
  groupée. La passe suivante lève le parcage et reprend le ticket. **Ne
  jamais reprendre ou déparquer un ticket à la main**, ni dispatcher
  `mol-ticket-resume`.
- **Pas repris** : un ticket arrêté ; un ticket dont la session du tour de
  correction est morte sans fermer son bead ; un ticket que la porte de fin
  de ticket laisse en attente (fidélité rouge, condition manquante).
- **Le convoi s'arrête de lui-même dans deux cas** (T21), lus dans `stop` :
  **branche d'intégration rouge** — plus aucun ticket ne démarre ni ne
  fusionne ; la passe publie un seul ticket `repair` qui cite le contrôle
  rouge, par la porte de patch, et ce `repair` est le seul ticket qu'elle
  démarre ; dès que le contrôle est vert (`repair` fusionné, ou branche
  protégée réparée), `./bin/spec-integration` retire le rouge et tout
  repart ; **deux Planning Exceptions ouvertes sur la Spec** — plus aucun
  nouveau ticket ne démarre, ceux en cours finissent ; y répondre
  (`./bin/escalation-door repondre`) relance les démarrages. **Ne jamais
  lever un rouge ni créer un `repair` à la main.**
- **Fin de Spec** (T23) : dès que tous les tickets du convoi sont fermés et
  que la branche d'intégration n'est pas rouge, la passe lance
  `./bin/spec-end run` et rapporte ses trois verdicts sous `spec_end`. Une
  condition non réunie est un résultat de la passe, pas un échec. Tests ou
  fidélité rouges : c'est le rouge ci-dessus, avec un tour de fin compté, et
  la passe suivante publie le `repair`. Quand Benjamin répond « faire
  réparer » à la demande sur un écart ou un « non fait », la passe publie ce
  `repair` aussi (`item_repairs`).
- **Deux tours de réparation en fin de Spec, puis une demande « non
  conforme »** (T26) : chaque refus d'une pointe en fin de Spec compte un
  tour, quelle que soit sa source — tests ou fidélité rouges, revue de fin
  défavorable, Outcome Evaluation qui n'observe pas une user story ou garde
  un constat hors ticket à réparer. Un seul compteur, borné à 2. Au refus
  suivant, **plus aucun `repair` de fin n'est publié** (ni celui d'un rouge,
  ni ceux de l'Evaluator, ni ceux de la revue de fin). L'arrêt vient plus
  tôt, avant le deuxième tour, si un tour n'a pas réduit le nombre de user
  stories non observées ou si la même user story est refusée deux fois. La
  passe fait alors générer le dossier de la pointe refusée
  (`./bin/evidence-pack`, en-tête « Dossier non conforme ») et t'envoie
  **une** demande : dans `./bin/escalation-door list`, la ligne
  `<convoi> — Demande « non conforme » — convoi <convoi> : <cause> — dossier : <chemin de la page>`.
  Ouvre la page, puis réponds par
  `./bin/escalation-door repondre <convoi> a|b|c` : **a** relancer un tour
  de réparation, **b** retourner à la planification, **c** abandonner.
  « Accepter » n'est jamais proposé : un Outcome non conforme ne s'accepte
  pas par cette demande. `non_conforme` dans la réponse de la passe dit où
  elle en est (`pending` tant qu'une Outcome Evaluation ou une revue de fin
  est encore en cours sur la pointe, `raised` une fois la demande partie).
  **Limites** : ta réponse est enregistrée mais rien ne la lit — le
  convoi reste arrêté et aucun tour ne repart (T29 ne traite que la réponse
  à un Delivered Outcome ; seul « abandonné » s'enregistre sur ce dossier,
  par `./bin/owner-answer`, `docs/OWNER_ANSWER.md`) ; si la passe échoue
  entre l'envoi et son enregistrement, tu reçois le même courrier une
  seconde fois (une seule ligne dans la liste).
- **Acceptance Request** (T28) : dès qu'un convoi est Delivered (les sept
  conditions de fin de Spec vertes sur un même commit), la passe t'envoie
  **une** demande, une fois par Delivered Outcome : dans
  `./bin/escalation-door list`, la ligne
  `<convoi> — Acceptance Request — convoi <convoi> : un Delivered Outcome attend votre jugement — dossier : <chemin de la page>`,
  avec une seule option (« Ouvrir l'Acceptance Session ») et aucune
  recommandation. Tu lances le produit par
  `./bin/acceptance-session open <convoi>`. Si le produit n'a pas démarré à
  l'ouverture d'une session, la passe suivante publie **un** `repair` qui
  rétablit ce démarrage (pas tant que les tours de fin sont arrêtés).
  `acceptance` dans la réponse de la passe dit ce qu'elle a fait
  (`action: requested`, `repair`). **Aucun délai ne répond à ta place** :
  rien n'est accepté, fusionné ni fermé sans ta réponse, qui s'enregistre
  par `./bin/owner-answer` (T29, `docs/OWNER_ANSWER.md`).
- **Constats rendus** (T29) : quand ta dernière réponse est « constats
  rendus », la passe suivante publie **un** `repair` par constat qui cite
  une user story ou une ancre de la Spec (`acceptance.owner_repairs`), le
  livre par le flux habituel, puis toute la porte de fin de Spec repasse à
  la nouvelle pointe et un nouveau dossier arrive avec une nouvelle
  Acceptance Request. Tant qu'un de ces `repair` n'est pas publié, ou que la
  Planning Exception du lot est ouverte, la fin de Spec attend
  (`acceptance.owner_hold`). **Limites** : la Planning Exception se traite
  par un Planning Run à la main, puis `./bin/owner-answer
  resolve-exception` — aucun code ne le lance ni ne prévient le Mayor.
- **Après « accepté » ou « abandonné » (T30)** : la passe suit ta réponse
  par `./bin/outcome-promote run` et ne fait rien d'autre sur ce convoi —
  une seule fusion de la branche d'intégration vers la branche protégée et
  la fermeture du convoi sur tes mots, ou la fermeture seule (`promotion`).
  Si la branche protégée a bougé et que les contrôles mécaniques rejoués
  sont rouges, ou s'il y a conflit, rien n'est fusionné : ton acceptation
  est annulée, la passe publie le `repair`, puis la fin de Spec repasse et
  une nouvelle Acceptance Request t'arrive. Un convoi fermé ainsi n'est
  plus parcouru. **Limites** : fusion par poussée directe, sans pull
  request ; rien ne te prévient d'une acceptation annulée.
- **Les bornes se règlent à un seul endroit** : `bounds` de
  `config/delivery-flow.json` — `resumes` (K, 3), `open_planning_exceptions`
  (2), `end_rounds` (tours de réparation de fin de Spec, 2). Changer une valeur change le comportement à la passe suivante ; une
  valeur absente ou mal formée est un refus. k (exécutions au vert) se règle
  par projet, dans son profil (`launch.k`).
- **Aucune relecture des tests** (ADR-0030 L3) : la passe n'en lance ni
  n'en règle aucune ; la revue de code lit les tests de critère.
- **Seule cette commande démarre un ticket d'un convoi marqué** :
  `./bin/dispatch-door` le refuse sans `--convoy` et le refuse à toute session
  d'agent, Mayor compris.
- **Ne jamais lancer `gc convoy control <ticket>`** : le dispatcher de contrôle
  de Gas City ne démarre pas les tickets d'un convoi, il ferme le bead qu'on lui
  donne s'il n'est pas un bead de contrôle (essai du 2026-10-06, Gas City 1.4.1).

Détail : `docs/CONVOY_ADVANCE.md`.

---

## `./bin/graph-review` — qui relit un graphe de tickets avant l'approbation de Benjamin ?

Un **relecteur de graphe** : une session neuve du rôle relecteur, en lecture
seule, qui n'a pas écrit le graphe (Spec af-wf4w5r §2, T08). Il ne concerne
qu'un brouillon qui déclare le contrat du nouveau flux (`flow_contract:
new-flow/v1`, `docs/ENTRY_CONTRACT.md`) ; tout autre brouillon est publié
comme avant (sortie 4, « pas un brouillon du nouveau flux »).

```bash
./bin/graph-review review <brouillon> --author-model <modèle>   # lance une passe et attend le verdict
./bin/graph-review remaining <brouillon> --text                # les refus restants, à trancher par Benjamin
./bin/graph-review decide <brouillon> --ticket T07 --decision publish|rework \
  --approved-by <approbateur> --project <projet> --words "<ses mots>"
./bin/graph-review check <brouillon>                           # ce que demande la porte de publication
./bin/graph-review show <brouillon>                            # toutes les passes, demandes et décisions
```

- **Qui la lance** : la session `/to-tickets`, avant l'approbation du
  brouillon, avec le modèle sur lequel elle tourne (`--author-model`).
- **Ce que rend une passe** : un verdict par ticket (démontrable seul,
  critères observables et falsifiables, taille tenable, tickets de même
  surface ordonnés, périmètre déclaré qui inclut les fichiers de branchement)
  et un verdict de graphe (aucune story orpheline, point d'assemblage non
  confisqué, Prototype Fold présent et premier). Le relecteur répond à des
  questions fermées ; le code calcule les verdicts et les lie au digest du
  brouillon.
- **Deux passes, pas trois** : une passe, les corrections avec Benjamin, une
  seule seconde passe. Une troisième demande est refusée (sortie 5) et rend
  la liste des refus restants.
- **Benjamin tranche** : chaque refus restant reçoit sa décision, ticket par
  ticket (`--graph` pour un refus sur le graphe), avec ses mots :
  `publish` (« publier tel quel ») ou `rework` (« à reprendre »). Seul
  l'approbateur humain déclaré du projet est accepté, et jamais sans mots.
- **Ce que la porte de publication refuse** (`./bin/ticket-graph-publish
  bd-publish`, rien n'est écrit) : aucune relecture ; un brouillon modifié
  depuis sa relecture ; une première passe qui refuse ; un refus restant sans
  décision, ou tranché `rework`.
- **Même modèle que l'auteur** : la relecture a lieu mais elle est signalée
  partout (`same_model: true`, « relecture non indépendante… »), jamais en
  silence. Tant que le rôle relecteur n'est essayé que sur Claude, un graphe
  écrit par une session Claude est signalé ainsi.
- **Sorties** : 0 fait ; 1 refus ou impossible, rien n'est écrit ; 4 pas un
  brouillon du nouveau flux ; 5 troisième passe refusée.
- **Ne jamais dispatcher `mol-graph-review` à la main** ni écrire les champs
  `gc.graph_review.*` du brouillon : cette commande est leur seul lecteur et
  leur seul écrivain.

Détail : `docs/GRAPH_REVIEW.md`.

---
## `./bin/evidence-capture` — d'où vient une preuve ?

D'un outil, jamais d'un agent (Spec af-wf4w5r §9, T09). Une preuve (Evidence
Record) est une pièce que l'outil enregistre lui-même : il exécute la
commande, ou pilote le navigateur, et note ce qu'il a obtenu, avec l'heure et
le commit. La pièce va dans le **magasin de preuves**, hors de tout dépôt Git,
rangée par Spec et par ticket ; son empreinte est inscrite sur le ticket dans
le tracker. Seulement pour un convoi qui porte la **marque du nouveau flux**.

```bash
./bin/evidence-capture command <convoi> <ticket> --piece <nom> --repo <dépôt> -- <commande…>
./bin/evidence-capture screenshot <convoi> <ticket> --piece <nom> --launch-state <relevé de project-launch> --path /
./bin/evidence-capture verify <convoi> <ticket> [--piece <nom>]
./bin/evidence-capture purge --spec <spec>
```

- **Mode commande** : la pièce contient la commande, sa sortie réelle, son
  code de sortie, l'heure et le commit. Aucune option ne permet de fournir la
  sortie : elle vient de l'exécution. Refus si le dépôt a des modifications
  non commitées.
- **Mode capture d'écran** : une adresse du produit lancé par
  `./bin/project-launch` seulement. La pièce contient l'image, l'adresse,
  l'heure et le commit lancé. Refus si le produit ne répond pas.
- **`verify`** échoue si le fichier du magasin ne correspond plus à
  l'empreinte du tracker, ou si la pièce n'a pas été produite par l'outil
  (fichier écrit à la main, même avec son empreinte inscrite dans le tracker).
- **`purge --spec`** retire les pièces de cette Spec et d'aucune autre ; à
  appeler après la promotion.
- **Où est le magasin** : `~/.local/state/agent-factory-evidence`
  (`EVIDENCE_STORE_DIR` pour le déplacer). L'outil refuse un magasin placé
  dans un dépôt Git.
- **Sorties** : 0 fait ; 1 refus, rien n'est écrit ; 4 « pas un convoi du
  nouveau flux ».
- **Navigateur** : `chrome-headless-shell` (cache Playwright), ou celui que
  nomme `EVIDENCE_CAPTURE_BROWSER`.
- **Limite** : l'agent choisit quoi capturer ; le scellé d'une pièce protège
  le chemin honnête, pas contre un processus du même compte Unix.

Détail : `docs/EVIDENCE_STORE.md`.

---

## `./bin/tdd-step` — les tests ont-ils été écrits d'abord ?

Un script le prouve, pas l'auteur (Spec af-wf4w5r §5, T10). Pour un ticket
d'un convoi qui porte la **marque du nouveau flux**, chaque étape vérifie la
branche du ticket à son dernier commit, enregistre son rapport comme pièce
du magasin de preuves, puis inscrit l'étape sur le ticket.

```bash
./bin/tdd-step red <convoi> <ticket> --repo <worktree> --profile <descripteur> --dataset <jeu> --base <commit de départ> --table <table critère → test>
./bin/tdd-step freeze <convoi> <ticket> --repo <worktree>
./bin/tdd-step green <convoi> <ticket> --repo <worktree> --profile <descripteur> --dataset <jeu>
./bin/tdd-step amend <convoi> <ticket> --repo <worktree> --profile <descripteur> --dataset <jeu> --reason "<raison>"
./bin/tdd-step prefactoring <convoi> <ticket> --repo <worktree> --profile <descripteur> --base <commit de départ>
```

- **Rouge** : seul le périmètre de test a changé depuis le commit de départ,
  chaque critère a un test, le produit lancé au commit de départ est en bonne
  santé, chaque test échoue par assertion et passe par un point d'entrée du
  produit. Un test en erreur, vide, ou qui ne demande rien au produit est
  refusé et nommé. Chaque test est prouvé selon le **mode du seam** par
  lequel il passe (boîte noire ou règle d'import, déclaré par seam dans le
  profil) ; le relevé nomme le seam et le mode de chaque test.
- **Critère déjà vert** (ADR-0030 L5) : un critère dont tous les tests
  passent au commit de départ est enregistré satisfait par le code existant
  (`satisfied` dans la preuve du rouge, scellée avec ce commit) et le ticket
  continue ; seul un ticket dont tous les critères sont déjà verts est
  arrêté (sortie 5), les critères nommés, l'arrêt écrit dans le tracker.
- **Gel** : suit la preuve du rouge au même commit, sans relecture des tests
  (ADR-0030 L3) ; les empreintes des tests, de la table et du harnais vont
  dans le magasin de preuves, hors de tout dépôt Git.
- **Vert** : refus si un fichier gelé a été modifié, supprimé ou déplacé ;
  sinon les tests gelés passent k fois de suite (k du profil ; 3 s'il n'en
  déclare pas). Un résultat mixte nomme le test instable.
- **Amendement** : le seul moyen de changer un test gelé, une fois par
  ticket, avec sa raison ; nouveau rouge, nouveau gel, diff enregistré. Le
  second arrête le ticket (sortie 5).
- **Prefactoring** : pas d'étape rouge ; la commande de régression passe
  avant et après ; aucun test existant n'est modifié. Sans aucun test au
  commit de départ, refus : d'abord des tests de caractérisation, dans un
  premier commit qui n'ajoute que des fichiers du périmètre de test ; ils
  passent sur le produit de départ et restent intouchés ensuite.
- **Sorties** : 0 étape prouvée ; 1 refus, rien n'est écrit ; 4 « pas un
  convoi du nouveau flux » ; 5 ticket arrêté.
- **Limite** : le script prouve l'ordre et les résultats, pas qu'un test
  observe bien son critère : c'est la question de la revue de code, posée
  après le vert (`./bin/code-review`, ADR-0030 L3). Lever un arrêt n'est pas
  dans cette commande.

Détail : `docs/TDD_STEP.md`.

---

## `./bin/ticket-exit` — comment un auteur termine-t-il son ticket ?

Par un appel structuré, jamais par du texte libre (Spec af-wf4w5r §5, T11).
Pour un ticket d'un convoi qui porte la **marque du nouveau flux**, chaque
sortie a une destination fixée par du code, et le compte rendu du ticket
(Ticket Handoff) est écrit dans le tracker.

```bash
./bin/ticket-exit exit <convoi> <ticket> --exit finished --repo <worktree> --handoff <compte rendu.json>
./bin/ticket-exit exit <convoi> <ticket> --exit planning_exception --repo <worktree> --handoff <compte rendu.json> --kind semantic|topology --summary "<la question>"
./bin/ticket-exit exit <convoi> <ticket> --exit operator_request --request <demande.json>
./bin/ticket-exit exit <convoi> <ticket> --exit technically_blocked --repair <ticket repair.json>
./bin/ticket-exit exit <convoi> <ticket> --exit interrupted --repo <worktree> [--handoff <partiel.json>]
./bin/ticket-exit read <convoi> <ticket>
./bin/ticket-exit deferral <convoi> <ticket> --repo <worktree>
```

- **Terminé** : refusé, pour un `vertical_slice` ou un `repair`, sans la
  preuve de démonstration capturée sur le produit lancé au commit de tête
  (`./bin/ticket-author demonstrate`) ; refusé sans les quatre rubriques du compte rendu (Fait,
  Écarts, Non fait, Constats hors ticket), chacune avec du contenu ou
  « aucun » ; refusé aussi tant que le diff du ticket porte un marqueur de
  report (TODO, FIXME, « not wired », « à brancher ») qu'aucun « non fait »
  ne déclare avec son fichier.
- **Planning Exception** et **demande opérateur** : le ticket et tous ceux
  qui l'attendent sont parqués ; la demande apparaît dans
  `./bin/escalation-door list`. Les tickets sans lien continuent de démarrer.
- **Planning Exception, le compte rendu d'abord** : refusée sans un compte
  rendu qui a ses quatre rubriques (le refus nomme celle qui manque, rien
  n'est écrit) ; le compte rendu est enregistré avant elle. Si elle nomme
  une ancre du prototype (`--anchor`), la rubrique « Écarts » doit
  mentionner cette ancre par son nom entier, sinon refus (`fixture` n'est
  pas nommée par `fixture.items` ni par `fixture:items`).
- **Bloqué technique** : un ticket `repair` est créé par du code et publié
  par la porte de patch ; il bloque le ticket, rien n'est parqué.
- **Interrompu** : la branche est poussée, un compte rendu partiel est
  enregistré. Une session terminée sans sortie est lue comme « interrompu ».
- **Relevés** : commits, fichiers touchés hors Declared Scope, preuve du
  rouge, marqueurs de report. L'auteur ne peut pas les fournir : ils sont
  calculés par le script et scellés dans le magasin de preuves.
- **`read`** : le ticket tel que son auteur le reçoit, avec le compte rendu
  de chaque bloqueur direct fermé.
- **Sorties** : 0 fait ; 1 refus ; 4 « pas un convoi du nouveau flux ».
- **Limite** : le détecteur est un filet par marqueurs ; un report écrit
  sans l'un de ces mots lui échappe. Reprendre un ticket ou lever un parcage
  n'est pas dans cette commande.

Détail : `docs/TICKET_EXIT.md`.

---

## `./bin/spec-integration` — où vont les tickets terminés d'une Spec ?

Dans la branche d'intégration de la Spec, un par un, jamais vers la branche
protégée (Spec af-wf4w5r §4 et §8, T18). Pour un convoi qui porte la
**marque du nouveau flux** seulement.

```bash
./bin/spec-integration open  <convoi> --repo <dépôt du projet> --protected <branche protégée>
./bin/spec-integration merge <convoi> --repo <dépôt du projet> --profile <descripteur.json> [--limit 1]
```

- **`open`** : crée `integration/<id de la Spec>` à la pointe de la branche
  protégée et l'enregistre sur le convoi. La porte de publication l'appelle
  dès que le convoi est marqué ; un convoi sans marque n'a pas de branche.
- **`merge`** : fusionne chaque ticket que son auteur a terminé à la pointe
  de sa branche, dans l'ordre du convoi, jamais deux à la fois. La branche
  d'intégration reprend d'abord la branche protégée. La commande de
  régression du profil tourne sur chaque résultat fusionné ; son relevé est
  une pièce du magasin de preuves (`merged_tests`), liée au commit du
  résultat. `./bin/convoy-advance` l'appelle à chaque passe, un ticket à la
  fois.
- **Pas de fusion sans revue de code favorable** : un ticket terminé n'est
  fusionné que si sa revue (`./bin/code-review`) est favorable à la pointe de
  sa branche. Sans revue, avec une revue en cours ou restée sans sortie, ou
  avec un Blocking Finding sans verdict favorable, il reste dans `waiting`
  avec la raison.
- **Pas de fusion sans Ticket Evaluation favorable** : même règle pour
  l'évaluation du produit lancé (`./bin/ticket-evaluation`) ; pour un
  `prefactoring`, c'est le contrôle que le produit démarre. Sans évaluation,
  avec une évaluation en cours, un critère « non observé » ou une panne de
  l'environnement, le ticket reste dans `waiting` avec la raison.
- **Conflit, ou tests rouges sur le résultat** : rien n'est fusionné ni
  poussé, le ticket retourne à son auteur. Aucun agent ne résout à sa place.
- **Branche d'intégration rouge** (T21) : quand la commande de régression est
  rouge une fois la branche protégée reprise, rien n'est poussé, aucun
  ticket n'est accusé, et le rouge est enregistré sur le convoi avec le
  contrôle cité (`integration_red` de `./bin/convoy-state show`). Tant qu'il
  y est, `merge` refuse (sortie 1, « branche d'intégration rouge ») et ne
  fusionne que le `repair` de ce rouge ; il retire le rouge dès que ce
  `repair` est fusionné vert, ou que le contrôle, rejoué quand une branche
  a bougé, est vert.
- **Commit ajouté après un verdict** (revue de code ou Ticket Evaluation) :
  fusion refusée, verdicts marqués invalides, une reprise comptée ; ils se
  rejouent sur la nouvelle pointe.
- **`take-up`** (T23, lancé par `./bin/spec-end`) : la branche
  d'intégration reprend la branche protégée et la commande de régression
  tourne sur le résultat, même sans rien à reprendre. Vert : la reprise est
  poussée, la pointe est rendue. Rouge : rien n'est poussé, le rouge est
  enregistré sur le convoi ; avec `--end-round`, un tour de fin est compté.
- **Sorties** : 0 fait ; 1 refus, ou un ticket refusé ; 3 état sans règle ;
  4 « pas un convoi du nouveau flux ».
- **Limites** : les autres conditions de la porte de fin de ticket ne sont
  pas encore exigées avant la fusion (T19) ; la session neuve de l'auteur d'un
  ticket retourné n'est pas démarrée ici : `./bin/convoy-advance` l'envoie à
  la passe suivante et compte une reprise (`docs/CONVOY_ADVANCE.md`) ; un
  seul dépôt par convoi.

Détail : `docs/SPEC_INTEGRATION.md`.

---

## `./bin/ticket-author` — qui tient la séquence d'un ticket du nouveau flux ?

Des scripts, jamais la parole de l'agent (Spec af-wf4w5r §0 règle 4, §4, §5,
T12). Un ticket d'un convoi qui porte la **marque du nouveau flux** est
travaillé par une session auteur neuve, dans son worktree, sur une branche
partie de la branche d'intégration de la Spec. La formule
`mol-ticket-author` enchaîne cinq étapes ; à chaque fermeture d'étape, Gas
City lance un contrôle, et c'est lui qui laisse démarrer la suivante.

```bash
./bin/ticket-author locate <ticket>
./bin/ticket-author start <convoi> <ticket>
./bin/ticket-author demonstrate <convoi> <ticket> --repo <worktree> --profile <profil> --dataset <jeu> -- <commande>
./bin/ticket-author gate <convoi> <ticket> --step workspace|red|code|demonstration|exit
./bin/ticket-author release <convoi> <ticket>
```

- **Personne ne lance la formule à la main** : `./bin/convoy-advance` démarre
  chaque ticket prêt (`start.formula` dans `config/delivery-flow.json`).
- **Étapes et contrôles** : prise du ticket (worktree, branche, session) ;
  rouge prouvé puis tests gelés (sans relecture : la revue de code les lit,
  ADR-0030 L3) ; tests verts à la pointe de la branche ; ligne
  de démonstration capturée sur le produit lancé, au commit de tête ; sortie
  de ticket enregistrée.
- **Contrôle refusé** : l'étape revient à la session avec le motif. Au bout
  de trois refus, la séquence échoue et les étapes restantes sont sautées :
  le code ne démarre jamais sans rouge prouvé.
- **Démonstration** : `demonstrate` lance le produit par son vrai point
  d'entrée et capture ce que l'auteur demande ; un commit de plus demande une
  nouvelle capture. Sans cette preuve, la sortie « terminé » est refusée.
- **Scope** : le Declared Scope ne borne rien. Un fichier touché hors scope
  est inscrit par du code dans les relevés du compte rendu.
- **Sous-agents** : une session auteur ne peut lancer que des sous-agents de
  lecture (`Explore`, `Plan`) ; tout autre lancement est bloqué par un hook.
  `./bin/role-adoption-trial run --role author` le prouve sur une session
  réelle. Limite : un sous-agent de lecture garde un shell.
- **Sorties** : 0 fait ou étape prouvée ; 1 refus ; 4 « pas un convoi du
  nouveau flux ».
- **Ticket arrêté** (critère déjà vert, second refus de la relecture des
  tests, relecture sans résultat) : chaque contrôle le refuse, la séquence
  échoue et rien n'en est fusionné.
- **Pas ici** : la revue de code (`./bin/code-review`) et la Ticket
  Evaluation sur le produit lancé (`./bin/ticket-evaluation`), que le flux
  envoie après la sortie « terminé » ; la porte de fin de ticket
  (`./bin/ticket-end`) ; la reprise d'un ticket, envoyée par
  `./bin/convoy-advance` à une session neuve sur la formule
  `mol-ticket-resume`, qui prend le ticket par le même `start`
  (`docs/CONVOY_ADVANCE.md`).

Détail : `docs/TICKET_AUTHOR.md`.

---
## `./bin/test-review` — un test de critère observe-t-il vraiment son critère ?

> **Remplacé par ADR-0030 L3** : le flux ne lance plus cette relecture ; la
> revue de code (`./bin/code-review`) lit les tests de critère. Retiré en L7.

Un **relecteur**, pas l'auteur, répond (Spec af-wf4w5r §5 « Relecture avant
gel », §8, T13). Entre le rouge prouvé et le gel, une session neuve du rôle
relecteur, en lecture seule, répond à une seule question par test de
critère : observe-t-il son critère, et échouerait-il sur l'observation qui
le rend faux ? Un test qui ne vérifie qu'un statut 200 est refusé. Ne
concerne qu'un ticket d'un convoi qui porte la **marque du nouveau flux**.

```bash
./bin/test-review review <convoi> <ticket> --repo <worktree>      # l'auteur, après tdd-step red
./bin/test-review show <convoi> <ticket>                          # les passes, la demande ouverte, l'arrêt
./bin/test-review settle <convoi>                                 # plus lancé par convoy-advance depuis ADR-0030 L3
./bin/test-review brief <convoi> <ticket>                         # la session relecteur (formule mol-test-review)
./bin/test-review record <convoi> <ticket> --verdict-file <f>     # la session relecteur
```

- **Sans verdict favorable, pas de gel** : `./bin/tdd-step freeze` refuse
  tant que chaque test de critère n'a pas passé la relecture, au même commit
  et sur les mêmes empreintes de fichiers. Sans gel, le code ne commence pas.
- **Un refus** : le relecteur donne une raison par test refusé. Le ticket
  retourne **une fois** à son auteur, qui corrige ses tests, les fait
  reprouver rouges et redemande la relecture.
- **Second refus** : le ticket est arrêté. Il apparaît **une seule fois**
  dans `./bin/escalation-door list`, avec le test et la raison.
- **Relecture plantée ou sans sortie** : elle n'est pas passée. Une relance,
  puis le ticket est arrêté et remonte de la même façon. Le délai d'un
  lancement est `test_review.timeout_seconds` dans
  `config/delivery-flow.json` (1800 s, valeur sans base mesurée).
- **Le verdict est calculé par du code** : le relecteur donne un état par
  test (`favorable` ou `unfavorable` avec sa raison), jamais un verdict
  global. Il ne reçoit que les critères du ticket et les tests ; rien
  d'autre de l'auteur.
- **Sans session d'auteur** : la relance, l'arrêt et la remontée sont aussi
  faits par `./bin/convoy-advance`, à partir du tracker seul.
- **Ne jamais dispatcher `mol-test-review` à la main** ni écrire
  `gc.flow.test_review` : seul `./bin/test-review` le fait, par
  `./bin/dispatch-door` et `./bin/convoy-state`.
- **Sorties de `review`** : 0 tests relus favorablement ; 2 refus, retour à
  l'auteur ; 5 ticket arrêté ; 6 pas encore de verdict, relancer la même
  commande ; 1 refus ou échec ; 4 « pas un convoi du nouveau flux ».
- **Limites** : rien ne lève encore un arrêt. Un test amendé après le gel
  n'est pas relu ici : la revue de code du ticket le relit
  (`./bin/code-review`).

Détail : `docs/TEST_REVIEW.md`.
## `./bin/code-review` — qui relit le code d'un ticket avant sa fusion ?

Un **relecteur**, jamais l'auteur (Spec af-wf4w5r §6, §8, T14). Dès qu'un
ticket est terminé et vert à la pointe de sa branche, le flux envoie son
diff commité à une session neuve du rôle relecteur, en lecture seule, qui
appelle le `code-review` de Matt inchangé. Ne concerne qu'un ticket d'un
convoi qui porte la **marque du nouveau flux**.

```bash
./bin/code-review show <convoi> <ticket>                      # les passes, la demande ouverte, le verdict, les modèles
./bin/code-review settle <convoi>                             # lancé par ./bin/convoy-advance à chaque passe
./bin/code-review brief <convoi> <ticket>                     # la session relecteur (formule mol-code-review)
./bin/code-review record <convoi> <ticket> --file <f>         # la session relecteur
./bin/code-review respond <convoi> <ticket> --file <f>        # la session neuve d'auteur, après un refus
```

- **Sans verdict favorable, pas de fusion** : `./bin/spec-integration merge`
  laisse le ticket dans `waiting` tant que sa revue n'est pas favorable à la
  pointe. Une revue absente, en cours, plantée ou sans sortie ne vaut pas
  accord.
- **Un constat ne bloque que s'il cite** une ligne de la Spec, du ticket ou
  une règle écrite du dépôt, et que la ligne citée s'y trouve. Un constat de
  goût donné comme bloquant est enregistré **non bloquant**, avec la raison.
- **Questions fermées sur les tests** : posées par du code (fichier de test
  hors des tests de critère gelés : passe-t-il par un seam listé ? test de
  critère amendé : observe-t-il encore son critère ?). Un « non » est un
  Blocking Finding.
- **Chaque Blocking Finding** reçoit « corrigé » (avec le commit) ou
  « contesté » (avec la raison) par `respond` ; une **seconde** session
  relecteur juge cette liste fermée contre le diff de correction.
- **Ce que reçoit le relecteur** (`brief`) : le diff, la Spec, le ticket, les
  standards du dépôt, les relevés des scripts. Ni le Handoff, ni la prose de
  l'auteur (sujets de commit et raison d'amendement retirés).
- **Modèles par rôle** : le modèle de l'auteur et celui du relecteur sont
  inscrits sur le ticket. S'ils sont identiques, ou si l'un n'est pas connu,
  la mention est enregistrée avec la revue, jamais omise.
- **Revue plantée ou sans sortie** : une relance, puis le ticket est arrêté
  et apparaît **une seule fois** dans `./bin/escalation-door list`. Le délai
  d'un lancement est `code_review.timeout_seconds` dans
  `config/delivery-flow.json` (3600 s, valeur sans base mesurée).
- **Le verdict est calculé par du code** : le relecteur ne rend jamais de
  verdict global.
- **Ne jamais dispatcher `mol-code-review` à la main** ni écrire
  `gc.flow.code_review` : seul `./bin/code-review` le fait, par
  `./bin/dispatch-door` et `./bin/convoy-state`.
- **Limites** : rien ne lève encore un arrêt ; la session neuve d'auteur qui
  corrige, son tour unique et l'arrêt d'un ticket encore refusé sont tenus
  par `./bin/correction-round`.

Détail : `docs/CODE_REVIEW.md`.

---

## `./bin/ticket-evaluation` — qui vérifie que le produit marche, avant la fusion d'un ticket ?

Un **Evaluator**, jamais l'auteur (Spec af-wf4w5r §7, §8, T15). Dès qu'un
ticket est terminé et vert à la pointe de sa branche, le flux lance le
produit **depuis une copie propre de cette pointe** (port isolé, jeux de
données synthétiques) et l'envoie à une session neuve du rôle Evaluator, en
lecture seule, qui l'utilise en boîte noire. Ne concerne qu'un ticket d'un
convoi qui porte la **marque du nouveau flux**.

```bash
./bin/ticket-evaluation show <convoi> <ticket>                 # les passes, la demande ouverte, les rôles, les produits encore lancés
./bin/ticket-evaluation verdict <convoi> <ticket>              # le verdict, recalculé : favorable ou non, et pourquoi
./bin/ticket-evaluation settle <convoi>                        # lancé par ./bin/convoy-advance à chaque passe
./bin/ticket-evaluation brief <convoi> <ticket>                # la session Evaluator (formule mol-ticket-evaluation)
./bin/ticket-evaluation record <convoi> <ticket> --file <f>    # la session Evaluator
```

- **Sans évaluation favorable, pas de fusion** : `./bin/spec-integration
  merge` laisse le ticket dans `waiting` tant que son évaluation n'est pas
  favorable à la pointe. Une évaluation absente, en cours ou sans résultat
  ne vaut pas accord.
- **Un état par critère et pour la ligne de démonstration** : « observé »
  (`observed`), « non observé » (`not_observed`) ou « inobservable »
  (`unobservable`), chacun avec une **preuve capturée** par
  `./bin/evidence-capture` sur le produit lancé. Un état sans preuve
  valide, une preuve prise ailleurs que sur ce produit, un critère
  reformulé ou retiré : refusés.
- **Le verdict est calculé par du code** : l'Evaluator ne rend jamais de
  verdict global. Favorable seulement si tout est « observé » avec preuve
  au commit de tête.
  - « non observé » : défavorable, retour à l'auteur.
  - « inobservable » par le critère : Planning Exception — une demande dans
    `./bin/escalation-door list`, le ticket et ceux qui l'attendent sont
    parqués. Un critère ne se dispense jamais.
  - « inobservable » par l'environnement : panne, non comptée comme refus ;
    l'évaluation est refaite une fois, puis le ticket est arrêté.
- **Ce que reçoit l'Evaluator** (`brief`) : la ligne de démonstration, les
  critères gelés, les adresses des produits lancés. Ni le Handoff, ni le
  diff, ni le dépôt.
- **`prefactoring`** : aucune session d'Evaluator. Du code lance le
  produit, capture la réponse de sa sonde, et enregistre qu'il démarre.
- **Fournisseur de l'Evaluator** : inscrit sur le ticket avec celui de
  l'auteur. S'il est le même, la mention « même fournisseur que l'auteur »
  est enregistrée, jamais omise. Si un autre fournisseur est déclaré et
  disponible pour le rôle, l'évaluation n'est pas lancée sur celui de
  l'auteur (`./bin/provider-failover` règle le rôle).
- **Évaluation sans résultat** : une relance, puis le ticket est arrêté et
  apparaît **une seule fois** dans `./bin/escalation-door list`. Le délai
  d'un lancement est `evaluation.timeout_seconds` dans
  `config/delivery-flow.json` (3600 s, valeur sans base mesurée).
- **Produits lancés** : une fois par jeu de données nommé du profil ; un
  profil qui n'en nomme aucun est refusé et rien n'est lancé. Ils restent
  debout entre deux passes, le temps de l'évaluation, puis du code les
  arrête. `show` liste ceux qui tournent encore (`live`).
- **Ne jamais dispatcher `mol-ticket-evaluation` à la main** ni écrire
  `gc.flow.evaluation` : seul `./bin/ticket-evaluation` le fait, par
  `./bin/dispatch-door` et `./bin/convoy-state`.
- **Limites** : rien ne lève encore un arrêt ; la session neuve d'auteur
  après un « non observé » et son tour unique sont tenus par
  `./bin/correction-round` ; les contrôles de
  fidélité d'un ticket qui touche un écran sont `./bin/prototype-fidelity`.

Détail : `docs/TICKET_EVALUATION.md`.

---

## `./bin/prototype-fidelity` — l'écran livré est-il fidèle au prototype que Benjamin a validé ?

Du code compare, état par état, la page livrée **servie à sa vraie adresse**
à la version figée du prototype (Validated Prototype), sans humain (Spec
af-wf4w5r §3, §7, §9, T16). Un écart mesurable est rouge et nommé ; il
n'arrive jamais jusqu'à Benjamin sans l'être.

```bash
./bin/prototype-fidelity check <descriptor.json> --prototype <dossier> --commit <sha> [--repo-root <dépôt du produit>]   # tous les écrans (fin de Spec)
./bin/prototype-fidelity check <descriptor.json> --prototype <dossier> --commit <sha> \
    --convoy <convoi> --ticket <ticket> [--screen <écran>]                                                              # un ticket : son écran seulement
```

- **Ce qui bloque** : un token du prototype absent ou changé (lu sur les
  sources), une ancre du prototype absente du livré, un autre élément, un
  autre emboîtement, un autre nombre d'occurrences, ou une autre valeur de
  style calculé sur une ancre (police, taille, graisse, interligne,
  couleurs, rayon, marges intérieures, affichage, ombre), à chaque taille
  d'écran et chaque thème de référence du prototype.
- **Sortie** : 0 vert (ou tout écart « accepté par Benjamin »), 1 rouge
  avec l'état, la taille d'écran, l'ancre et la propriété de chaque écart,
  2 refus, 4 convoi sans la marque du nouveau flux.
- **Jamais vert sur ce qui n'a pas été comparé** : un état prototypé que le
  profil ne sert sur aucun écran, un produit qui ne démarre pas, un
  navigateur sans mesure : refus, pas un vert.
- **Avec un ticket** : le relevé complet est une pièce scellée du magasin
  de preuves ; les captures côte à côte et l'image de différence de chaque
  état sont enregistrées par `./bin/evidence-capture comparison`, les deux
  côtés rendus à ce moment-là ; le résultat est écrit sur le ticket par
  `./bin/convoy-state set-fidelity`, lié au commit.
- **Les captures ne bloquent jamais** : le nombre de pixels différents est
  noté, aucun seuil n'existe. Elles servent aux yeux de Benjamin.
- **Un écart voulu** ne se lève pas ici, et pas par l'auteur : l'auteur
  sort par `./bin/ticket-exit exit … --exit planning_exception --anchor
  <ancre>`, après avoir écrit l'écart et son ancre sous « Écarts » dans son
  compte rendu (sinon refus) ; la demande propose à Benjamin « Accepter l'écart sur l'ancre
  … » ; sa réponse par `./bin/escalation-door repondre` fait lire l'écart
  « accepté par Benjamin ». Toute autre réponse le laisse rouge. Un écart
  de token se répare.
- **Écrans** : déclarés dans le profil du projet (`launch.screens` : nom,
  chemin servi, états prototypés).
- **Limites** : le lien ticket → écran n'est pas enregistré à la
  publication (l'appelant nomme l'écran) ; l'appel avant la fusion d'un
  ticket est fait par `./bin/ticket-end`, celui de fin de Spec par
  `./bin/spec-end` ; le texte affiché n'est pas
  comparé ; un produit qui interdit d'être encadré ne se mesure pas.

Détail : `docs/PROTOTYPE_FIDELITY.md`.
## `./bin/correction-round` — que se passe-t-il quand la revue ou l'évaluation refuse un ticket ?

**Un seul tour de correction, puis l'arrêt** (Spec af-wf4w5r §8, T17). La
revue de code et la Ticket Evaluation d'un ticket terminé tournent en
parallèle sur la même pointe. Quand les deux ont répondu et qu'au moins
l'une refuse, le flux envoie **tous leurs constats à une seule session neuve
d'auteur**. Ne concerne qu'un ticket d'un convoi qui porte la **marque du
nouveau flux**.

```bash
./bin/correction-round show <convoi> <ticket>      # le tour, les dérogations, l'arrêt, les compteurs
./bin/correction-round override <convoi> <ticket> --finding F1.1 --approved-by <approbateur> --words "…"   # Benjamin, sur un ticket arrêté
./bin/correction-round settle <convoi>             # lancé par ./bin/convoy-advance à chaque passe
./bin/correction-round brief <convoi> <ticket>     # la session d'auteur du tour (formule mol-ticket-correction)
```

- **Un tour par ticket**, commun à la revue et à l'évaluation. Il compte
  dans les reprises du ticket (`resumes` et `correction_rounds` dans
  `./bin/convoy-state show`).
- **Une seule session** : tant que l'une des deux n'a pas répondu, aucune
  session ne démarre. Son `brief` contient les Blocking Findings de la
  revue et ce que l'évaluation n'a pas observé.
- **Encore refusé après ce tour, le ticket s'arrête** (`still_refused`) :
  aucun second tour, rien ne fusionne, et le ticket apparaît **une seule
  fois** dans `./bin/escalation-door list`, que la revue, l'évaluation ou
  les deux l'aient refusé.
- **Dérogation** (`override`) : sur un ticket arrêté, l'approbateur humain
  déclaré du projet (`human_approver` de `config/projects/<projet>.toml`)
  peut passer outre **un Blocking Finding de la revue**, avec ses mots, non
  vides. Elle est ensuite lue « dérogation enregistrée ». Refusée de
  quiconque d'autre, sans mots, ou sur un ticket qui n'est pas arrêté.
- **Un critère non observé ne se dispense jamais** : `override --criterion`
  est refusé, et le message renvoie à la Planning Exception
  (`./bin/planning-exception`).
- **La dérogation ne lève pas l'arrêt** : quand tous les Blocking Findings
  restés sans verdict favorable sont dérogés, la passe suivante fusionne le
  ticket et la porte de fin de ticket le ferme (`./bin/ticket-end`,
  condition 9).
- **Ne jamais dispatcher `mol-ticket-correction` à la main** ni écrire
  `gc.flow.correction` ou `gc.flow.overrides` : seul
  `./bin/correction-round` le fait, par `./bin/dispatch-door` et
  `./bin/convoy-state`.
- **Limites** : aucun délai sur la session de correction (une session morte
  sans fermer son bead laisse le ticket en attente : les reprises de
  `./bin/convoy-advance` ne la couvrent pas) ; rien ne lève un arrêt, et un
  ticket arrêté n'est jamais repris. Le tour compte parmi les trois reprises
  qui parquent un ticket (`docs/CONVOY_ADVANCE.md`).

Détail : `docs/CORRECTION_ROUND.md`.

---

## `./bin/proposal-door` — la porte unique des propositions

Toute proposition d'amélioration passe par cette porte (T07) : jamais de
`gc bd create -l proposal` à la main. Elle refuse l'écriture (aucun bead)
si un champ manque, dépasse 140 caractères sur une ligne ou n'est pas dans
la langue de l'opérateur.

```bash
./bin/proposal-door create '<json>'            # quoi, pourquoi, que_faire[], langue, classe
./bin/proposal-door accepter <bead> <acteur>   # -> à planifier
./bin/proposal-door rejeter <bead> <raison> <acteur>
./bin/proposal-door reporter <bead> <heure> <acteur>
./bin/proposal-door reconvertir <bead> <raison> '<que_faire json>' <acteur>
./bin/proposal-door compte [--classe maintenance|decision|sans_champs]
./bin/proposal-door list   [--classe ...]      # "<bead>\t<classe>\t<état>\t<quoi>"
```

**Deux classes** (ADR-0029, Benjamin 2026-10-07 : « oui pour R1 »), choisies
par le producteur à la création ; en cas de doute, `decision` :

| Classe | Ce que c'est | Ce que fait la porte | Où le Cockpit le montre |
|---|---|---|---|
| `maintenance` | corrige un défaut constaté de l'usine sans changer ce que l'opérateur voit ou doit faire, ni une règle de méthode (ordres, gardes, formules, tests, docs, filtres, seuils) | crée un bead bug (`gc.authorized_by=ADR-0029`, `gc.source=proposal-door`, label `maintenance`), le relie à la proposition, passe la proposition en `prise_en_charge` (tracé) et envoie un mail au Mayor, qui le dispatche par `factory-work-dispatch` | zone santé (« L'usine corrige seule N défaut(s) … ») et journal ; jamais dans « Ce qui t'attend » |
| `decision` | change ce que l'opérateur voit ou doit faire, une règle de méthode, une dépense, un consentement, une donnée personnelle, un effet irréversible, un comportement produit | exige exactement une option `recommande: true` avec sa `raison`, sinon refus | « Ce qui t'attend », Quand tu veux |

Une proposition sans champs (créée avant la porte) n'est jamais réécrite :
le Cockpit la signale en zone santé « à reformuler par la porte ou à
fermer ». Un bead `maintenance` qui, en cours de travail, touche un
comportement visible de l'opérateur est **arrêté, jamais poursuivi** :
`reconvertir` ferme le bead bug et refait de la proposition une `decision`
(ADR-0029 point 6). ADR-0017 reste vrai : la porte n'autorise que la
correction du défaut constaté, jamais un refactor ou un audit.

Pourquoi : le 2026-10-07, sur 8 propositions ouvertes dans le Cockpit, 5
étaient des filtres d'ordres ou de gardes que l'autorisation de maintenance
du 2026-09-16 couvrait déjà, et 4 étaient périmées. Benjamin arbitrait des
décisions qui n'étaient pas de son niveau.

Tests : `tests/proposal-door-test.py` (la porte sur un faux `gc`),
`tests/proposal-classes-contract-test.py` (la vraie porte puis le vrai
Cockpit sur les mêmes beads).

---
## `./bin/ticket-end` — pourquoi ce ticket n'est-il pas fermé ?

**La porte de fin de ticket** (Spec af-wf4w5r §9, T19). Dans un convoi qui
porte la **marque du nouveau flux**, un ticket ne se ferme que par cette
porte : une liste fermée et versionnée de **neuf conditions**. Une PR
fusionnée et une CI verte ne ferment rien, et l'auteur ne ferme jamais son
ticket.

```bash
./bin/ticket-end check <convoi> <ticket> --repo <dépôt du projet>                  # les neuf verdicts ; n'écrit rien
./bin/ticket-end check <convoi> <ticket> --repo <dépôt du projet> --before-merge   # ce que la fusion exige
./bin/ticket-end settle <convoi> --repo <dépôt du projet>                          # lancé par ./bin/convoy-advance après la fusion
./bin/ticket-end fidelity <convoi> --repo <dépôt du projet> --profile <profil>     # lancé par ./bin/convoy-advance avant la fusion
```

- **Les neuf conditions** (liste `ticket-end/v1`), lues à la pointe de la
  branche du ticket : 1 critères identiques au digest approuvé ; 2 Handoff
  valide avec preuve du rouge et de démonstration ; 3 Ticket Evaluation
  favorable (prefactoring ou ticket sans interface, ADR-0030 L4 : le produit
  démarre) ; 4 fidélité verte si le
  ticket touche un écran ; 5 détecteur de report passé ; 6 fusionné dans la
  branche d'intégration, tests verts sur le résultat ; 7 preuves scellées,
  liées à la pointe fusionnée ; 8 preuve TDD enregistrée ; 9 revue favorable
  ou dérogation enregistrée.
- **Pour savoir ce qui manque** : `check` nomme chaque condition non réunie
  et dit ce qui a été lu. Rien n'est écrit lors d'un refus.
- **Avant la fusion** : `./bin/spec-integration merge` ne fusionne un ticket
  que si les conditions 1 à 5 et 7 à 9 sont réunies ; sinon le ticket attend,
  avec le texte de la porte. La condition 6 se vérifie après.
- **Fermeture** : la passe qui fusionne un ticket le ferme si les neuf
  conditions sont réunies. Le relevé de la porte (commit fusionné, version
  de la liste, neuf verdicts) et le statut fermé sont écrits ensemble ; il se
  lit sous `gates.ticket_end` dans `./bin/convoy-state show`.
- **Ticket d'interface** : avant la fusion, la passe lance le contrôle de
  fidélité sur le commit qui fusionne, contre le Validated Prototype que le
  ticket nomme.
- **Ne jamais fermer à la main un ticket d'un convoi marqué** (`gc bd
  close`, `./bin/deliver-close`) : `./bin/deliver-close` le refuse, et une
  fermeture hors porte arrête le convoi (incident d'usine). `close` et
  `settle` sont refusés à toute session d'agent.
- **Un convoi sans marque** garde `./bin/deliver-close`, sans changement.
- **Limites** : une fidélité rouge, comme toute condition manquante, laisse
  le ticket en attente : les reprises de `./bin/convoy-advance` ne couvrent
  pas un ticket que la porte laisse ouvert (`docs/CONVOY_ADVANCE.md`) ; un
  contrôle de fidélité par passe ; la fin de Spec se vérifie par
  `./bin/spec-end`.

Détail : `docs/TICKET_END.md`.

---

## `./bin/ci-minutes` — combien de minutes GitHub Actions la CI de l'usine a-t-elle consommées ?

**Les minutes facturées, par jour et par run** (af-mzuprx). Le dépôt est
privé : chaque minute de runner est facturée, chaque job arrondi à la minute
supérieure. L'API `timing` de GitHub répond 0 et l'API de facturation exige
un jeton `admin:org` que l'usine n'a pas : ce script lit le début et la fin
de chaque job et applique lui-même la règle. Lecture seule.

```bash
./bin/ci-minutes                       # les 3 derniers jours, et le détail des 15 derniers runs
./bin/ci-minutes --since 2026-10-06    # depuis un jour donné
./bin/ci-minutes --runs 40             # plus de runs détaillés
```

- **Jours et heures** : Europe/Paris.
- **Colonnes** : runs, minutes, dont `pull_request`, dont `push`, dont
  autres, et minutes des runs qui n'ont pas fini verts.
- **Un job qui n'a jamais eu de runner** (quota atteint) compte 0.
- **Quels tests coûtent le plus** : chaque ligne de `./bin/ci-run-tests`
  finit par les secondes du fichier ; elles se lisent dans le journal du job.
- **Ce que le script ne dit pas** : le quota restant et le montant facturé.
  Ils se lisent sur la page d'usage GitHub de l'organisation.

Détail : `docs/OPERATIONS.md`, « Factory CI cost and the Actions quota ».

---
## `./bin/ci-test-seconds` — pourquoi « Tests » attend-il les autres lots ?

**La durée mesurée de chaque fichier de test** (af-mzuprx). La CI de l'usine
répartit les tests en lots, un runner par lot. `./bin/ci-run-tests --shard`
donne chaque fichier, du plus long au plus court, au lot le moins chargé, en
lisant `config/ci-test-seconds.tsv`. Ce script réécrit cette liste à partir
des journaux d'un run vert.

```bash
./bin/ci-test-seconds              # depuis le dernier run vert de Factory CI
./bin/ci-test-seconds --run <id>   # depuis un run donné
```

- **Quand le lancer** : quand l'étape « Wait for the other lots » du job
  `Tests` affiche un avertissement (plus de 3 minutes d'attente, facturées).
- **Où** : dans un arbre de travail, jamais dans la racine vive ; le fichier
  réécrit passe par une pull request.
- **Liste périmée ou absente** : les lots sont moins égaux, rien d'autre. Un
  fichier absent de la liste est pesé par sa taille ; chaque fichier reste
  dans exactement un lot.

Détail : `docs/OPERATIONS.md`, « Factory CI cost and the Actions quota ».

---
## `./bin/factory-revive` — relancer un superviseur que personne n'a arrêté exprès

**Un arrêt non demandé est relancé en 7 minutes au plus** (af-v9t5vz). Le
2026-10-08 à 04:27 (Paris), le script d'essai d'un ouvrier a lancé `gc
supervisor stop` sur l'usine vivante. systemd a vu un arrêt propre (code 0)
et n'a rien relancé, `bin/factory-boot` ne tourne qu'à l'ouverture de session
Windows, et tous les orders sont morts avec le superviseur : l'usine est
restée arrêtée 56 minutes.

```bash
./bin/factory-revive check       # verdict seul, ne touche à rien (sort 1 si arrêt non demandé)
./bin/factory-revive run         # ce que le minuteur appelle
./bin/factory-revive install     # écrit et active le minuteur systemd utilisateur (une fois, sur accord de l'opérateur)
./bin/factory-revive uninstall   # le retire
```

Ce qui distingue un arrêt non demandé d'un arrêt délibéré : l'arrêt délibéré
du runbook (§2) commence par `gc stop`, qui retire la cité de la liste du
superviseur (`~/.gc/cities.toml`).

| État constaté | Ce que fait `run` |
|---|---|
| le superviseur répond | rien |
| superviseur arrêté, cité absente de la liste | rien : arrêt délibéré (une ligne au journal, une seule) |
| superviseur arrêté, cité encore dans la liste, toujours vrai 45 s plus tard | `bin/factory-boot`, puis un ticket `maintenance` et une escalade « Mayor d'abord » par `bin/escalation-door` (promue à Benjamin au bout de 2 h si rien n'est élucidé) |
| `factory-boot` n'a pas ramené le superviseur | sort 1, nouvel essai au passage suivant |

- **Délai** : minuteur toutes les 5 min + 45 s de confirmation + le temps de
  `factory-boot` (environ 1 min), soit 7 minutes au plus.
- **Ne défait jamais un arrêt délibéré** : il ne relance que par
  `factory-boot`, qui laisse suspendue une cité suspendue ; il n'arrête, ne
  suspend et ne désenregistre rien.
- **Pourquoi un minuteur systemd et pas un order** : un order tourne dans le
  superviseur, donc pas quand il est arrêté.
- **Ce qu'il ne voit pas** : un `gc stop` de la cité vivante lancé par erreur
  (il ressemble à un arrêt délibéré), et une usine qui tourne mais n'avance
  pas (c'est le rôle de `factory-watchdog` et de la ligne « Usine à l'arrêt ? »
  du cockpit). Si le minuteur lui-même ne tourne pas, il reste l'alerte
  externe « Usine muette » du cockpit.
- **Journal** : `.gc/runtime/factory-revive.log`.

Le même correctif fait démarrer le superviseur par son unité systemd dans
`bin/factory-boot` quand elle est installée, au lieu de `gc supervisor
start` : ce dernier lance un superviseur hors de l'unité, que `gc start`
réactive ensuite et qui redémarre alors en échec toutes les 5 secondes.

Côté tests : aucun test n'arrête une cité ou un superviseur autrement que par
`isolated_city_stop` (`tests/lib/isolated-city.sh`), qui refuse si `GC_HOME`
n'est pas dans le répertoire de l'essai.

Tests : `tests/factory-revive-test.sh`, `tests/factory-boot-supervisor-test.sh`,
`tests/isolated-city-stop-guard-test.sh`. Runbook :
`docs/RUNBOOK_STOP_AND_RESTART.md` §3.

---
## `./bin/spec-end` — la Spec est-elle vérifiée, et sinon que manque-t-il ?

**La porte de fin de Spec** (Spec af-wf4w5r §9 et §8, T23, T24, T25, T27 et T26). Dans un
convoi qui porte la **marque du nouveau flux**, des tickets tous fermés ne
font pas une Spec vérifiée : du code rend **trois verdicts mécaniques, tous
liés au même commit** de la branche d'intégration, la branche protégée
reprise. Aucun agent ne les rend. Sur ce même commit, elle lit ensuite
l'Outcome Evaluation et les constats hors ticket (`./bin/outcome-evaluation`),
et la revue de code de fin (`./bin/spec-end-review`).

```bash
./bin/spec-end check <convoi> --repo <dépôt du projet>                      # où en est la fin de Spec ; n'écrit rien
./bin/spec-end run   <convoi> --repo <dépôt du projet> --profile <profil>   # la porte ; lancée par ./bin/convoy-advance
```

- **Les sept conditions** (liste `spec-end/v4`), dans l'ordre : 1 registre
  (tickets fermés par la porte de fin de ticket ou retirés, aucun parqué ;
  chaque écart et chaque « non fait » d'un Ticket Handoff « réparé » ou
  « accepté par Benjamin » ; aucune Planning Exception ouverte) ; 2 tests
  verts sur la pointe, branche protégée reprise ; 3 fidélité mécanique verte
  sur toutes les ancres de tous les états prototypés ; 4 Outcome Evaluation
  (chaque user story numérotée « observée avec preuve » sur le produit
  assemblé, aucun constat hors ticket non classé) ; 5 constats hors ticket
  tous dans un état final ; 6 revue de code de fin complète et favorable sur
  tout le diff assemblé, à ce commit précis ; 7 Evidence Pack généré par du
  code, complet et à jour, à ce commit (`./bin/evidence-pack`). Une condition non réunie arrête
  la porte : les suivantes ne sont pas lancées — sauf la revue de fin, faite
  en parallèle de l'Outcome Evaluation et lue quoi que disent 4 et 5. Seuls
  les verdicts 1 à 3 sont enregistrés ; 4 à 7 sont relus à chaque appel. La
  porte ne génère pas le dossier : `./bin/convoy-advance` le fait générer
  quand il ne manque que lui.
- **Pour savoir ce qui manque** : `check` nomme chaque condition non réunie
  et dit ce qui a été lu.
- **Un écart ou un « non fait » sans état final** : la porte le nomme et te
  pose une question, une fois par ticket (`./bin/escalation-door list`).
  Réponds par `./bin/escalation-door repondre <ticket> a` (faire réparer :
  du code publie un ticket `repair`) ou `b` (accepter tel quel). **Aucune
  commande n'écarte un élément** : il finit réparé ou accepté par toi.
- **Tests rouges ou fidélité rouge** : c'est le rouge de la branche
  d'intégration ; un tour de fin est compté (`counters.end_rounds`) et
  `./bin/convoy-advance` publie le seul `repair`. La porte rejoue tout une
  fois ce `repair` fusionné et fermé.
- **Deux tours de réparation, pas plus** (T26) : les tours de fin sont un
  seul compteur pour toutes les sources (tests ou fidélité rouges, revue de
  fin, Outcome Evaluation), borné par `bounds.end_rounds` de
  `config/delivery-flow.json` (2, sans base mesurée). Un rouge trouvé une
  fois les tours consommés est enregistré **avec l'arrêt des tours**, sans
  tour de plus et sans `repair` : la condition rouge le dit, et tu reçois
  une demande « non conforme » (`./bin/convoy-advance`). Sous ce rouge, la
  porte refuse en disant qu'elle attend cette demande.
- **Delivered** (T26) : quand les sept conditions sont vertes sur la même
  pointe, dossier compris, `run` l'enregistre sur le convoi
  (`convoy.delivered` dans `./bin/convoy-state show`) et répond
  `"delivered": true` ; `check` le dit aussi, tant que rien n'a bougé.
  Jamais avec une condition rouge, sans dossier, sur un dossier généré
  pendant qu'une condition était rouge, ni pour un commit de plus.
  **Delivered est un état du convoi, pas une acceptation** : rien n'est
  fusionné dans la branche protégée, rien n'est fermé, rien n'est accepté à
  ta place.
- **Un commit de plus annule tout** : les verdicts sont enregistrés avec
  leur commit (`convoy.spec_end` dans `./bin/convoy-state show`). Dès que la
  branche d'intégration ou la branche protégée bouge, `check` les dit
  « périmés » et la porte rejoue tout.
- **Sorties** : 0 sept conditions réunies sur la pointe actuelle ; 1 refus ou
  condition non réunie ; 3 état sans règle ; 4 convoi sans marque. `run` est
  refusé à toute session d'agent.
- **Limites** : la porte tourne dans la passe de l'ordre (délai de 300 s,
  non mesuré sur un vrai projet) ; pas de pièce scellée pour les tests et la
  fidélité de fin (leur relevé est sur le convoi) ; la porte vérifie, elle
  n'accepte rien et ne ferme rien (ta réponse : `./bin/owner-answer` ; la
  fusion et la fermeture : `./bin/outcome-promote`, qui appelle ici
  `replay` — les seuls contrôles mécaniques, sans tour de fin compté —
  quand la branche protégée a bougé depuis ton jugement) ; une fois les
  tours arrêtés, aucune commande ne les relance
  encore, quelle que soit ta réponse à la demande « non conforme » ; sous
  un rouge de fin, `check` montre les conditions 2 à 7 « non lancé » au lieu
  de nommer celle qui est rouge (lis `end_stop` et
  `./bin/convoy-state show`).

Détail : `docs/SPEC_END.md`.

---

## `./bin/outcome-evaluation` — le produit assemblé fait-il ce que la Spec demande, story par story ?

**L'Outcome Evaluation et le classement des constats hors ticket** (Spec
af-wf4w5r §7 et §9 points 4 et 5, T24). Dans un convoi qui porte la **marque
du nouveau flux**, une fois les trois verdicts mécaniques de `./bin/spec-end`
verts sur un commit, un Evaluator de fin — contexte neuf, boîte noire, rôle en
lecture seule — utilise le produit assemblé lancé par du code à ce commit. Il
rend **un état et une preuve par user story numérotée** ; **le verdict est
calculé par du code**.

```bash
./bin/outcome-evaluation show    <convoi>   # états, preuves, repairs rédigés, contradictions ; n'écrit rien
./bin/outcome-evaluation verdict <convoi>   # le verdict calculé et ses raisons ; n'écrit rien
```

- **Verdict** : favorable seulement si chaque story est « observée avec
  preuve » au commit de la porte. Une story manquante ou sans preuve valide
  fait refuser l'enregistrement.
- **Story « non observée »** : l'Evaluator rédige un `repair` qui cite la
  story et ne le publie pas ; `./bin/convoy-advance` le publie par la porte
  de patch. **Story inobservable** : l'évaluation s'arrête et une question
  t'est posée (`./bin/escalation-door list`).
- **Constats hors ticket** : chacun est classé « réparé » (citation de ce
  qu'il rétablit et repair rédigé obligatoires), « proposition pour
  Benjamin » (gardé pour le dossier) ou « écarté » (raison obligatoire). Un
  constat non classé fait refuser la porte de fin de Spec, qui le nomme.
- **Contradiction** : une story « non observée » dont tous les tickets
  couvrants étaient « observés » est inscrite par du code (`show`,
  `contradictions`).
- **Exploration libre et écarts de fidélité** : enregistrés, sans effet sur
  le verdict.
- **Arrêts** : aucun résultat après une relance, environnement en panne,
  story inobservable — une demande t'est adressée, une fois.
- **Sorties** : 0 fait ; 1 refus ; 3 état sans règle ; 4 convoi sans marque.
- **Tours de fin bornés** (T26) : une évaluation qui laisse une user story
  non observée, ou un constat hors ticket à réparer, compte un tour de fin
  (`counters.end_rounds`, borne 2, compteur commun aux rouges mécaniques et
  à la revue de fin). Les tours s'arrêtent **avant le deuxième** si le tour
  précédent n'a pas réduit le nombre de user stories non observées, ou si
  une user story déjà refusée l'est de nouveau ; sinon à la borne. Arrêtés,
  les `repair` rédigés ne sont plus publiés et tu reçois une demande « non
  conforme » avec le lien du dossier (`./bin/convoy-advance`).
- **Limites** : l'arrêt anticipé ne lit que les user stories non observées,
  pas les constats hors ticket ; aucun essai avec
  une vraie session d'Evaluator ; le dossier n'est pas généré ici.

Détail : `docs/OUTCOME_EVALUATION.md`.

---

## `./bin/spec-end-review` — le diff assemblé d'une Spec a-t-il été relu, et qu'a dit la revue ?

**La revue de code de fin** (Spec af-wf4w5r §6 « Fin de Spec », §9 point 4,
T25). Deux tickets, corrects chacun, peuvent se contredire une fois
assemblés : aucune revue par ticket ne le voit. Quand la porte de fin de
Spec a rendu ses trois verdicts mécaniques sur un commit, le flux — jamais
un auteur — envoie **tout le diff de la branche d'intégration contre la
branche protégée** à une session neuve du rôle relecteur, en lecture seule.
Ne concerne qu'un convoi qui porte la **marque du nouveau flux**.

```bash
./bin/spec-end-review show <convoi>      # où en est la revue de fin : passes, demande, arrêt, tour compté ; n'écrit rien
./bin/spec-end-review settle <convoi>    # ce qui est dû ; lancé par ./bin/convoy-advance à chaque passe
```

- **Mêmes règles que la revue d'un ticket** : un constat ne bloque que s'il
  cite une ligne de la Spec, d'un ticket du convoi ou une règle écrite du
  dépôt, et que du code retrouve cette ligne dans sa source. L'issue est
  calculée, jamais donnée par le relecteur.
- **Un Blocking Finding devient un ticket `repair`** rédigé par le
  relecteur ; `./bin/convoy-advance` le publie par la porte des tickets
  ajoutés et il suit le flux d'un ticket ordinaire. Pas de « corrigé /
  contesté » à la fin.
- **Rejouée en entier à chaque nouvelle pointe** : le `repair` fusionné
  déplace la pointe, la porte rejoue ses verdicts et une autre session relit
  tout le diff. Un verdict d'un tour précédent n'est jamais réutilisé.
- **La porte de fin de Spec refuse sans elle** : revue absente, en cours,
  arrêtée, liée à un autre commit, ou avec un Blocking Finding
  (`./bin/spec-end check` dit lequel).
- **Une sortie incomplète compte non passée** : un axe ou un fichier du diff
  non relu, pas de sortie dans le délai (7200 s, sans base mesurée), bead
  fermé sans sortie. Une relance, puis la revue est arrêtée et te remonte
  une fois (`./bin/escalation-door list`). Chaque passe garde sa durée et
  les fichiers non relus.
- **Un tour de fin est compté** par revue défavorable, une fois par pointe
  (`counters.end_rounds`) — le même compteur que les rouges mécaniques et
  l'Outcome Evaluation, borné à 2 (`bounds.end_rounds`, T26). Une revue
  défavorable une fois les tours consommés n'en compte pas : les tours sont
  arrêtés, ses `repair` rédigés ne sont pas publiés et tu reçois une demande
  « non conforme » (`./bin/convoy-advance`).
- **Indépendance** : `show` dit si le relecteur tourne sur le modèle d'un
  auteur, ou si un modèle n'est pas relevé.
- **Limites** : les constats restent le jugement d'un agent ; la couverture
  est déclarée par le relecteur ; rien ne lève un arrêt de la revue sur sa
  pointe ; pas d'arrêt anticipé sur les constats de revue : un même constat
  relevé deux fois de suite coûte un tour, l'arrêt avant la borne n'existe
  que pour les user stories non observées.
- **En même temps que l'Outcome Evaluation** : la passe qui rend les trois
  verdicts lance les deux sur le même commit ; aucune n'attend l'autre.

Détail : `docs/SPEC_END_REVIEW.md`.

---
## `./bin/ci-runner` — la CI de l'usine tourne-t-elle sur le PC, et le runner est-il debout ?

**Le côté opérateur du runner auto-hébergé** (af-r1ymfm). Un *runner* est la
machine qui exécute les jobs de GitHub Actions ; celui-ci est le PC lui-même,
donc 0 minute facturée. Chaque job tourne dans un conteneur jetable, sous un
utilisateur Linux sans droits (`factory-ci`), limité à 4 cœurs et 4 Go.

```bash
./bin/ci-runner status            # services, où vont les runs, runner vu par GitHub, runs en attente
./bin/ci-runner pause             # plus de nouveau job (celui en cours se termine)
./bin/ci-runner pause --now       # tue aussi le job en cours : son run finit rouge
./bin/ci-runner resume
./bin/ci-runner mode github       # renvoie la CI sur les runners GitHub, facturés
./bin/ci-runner mode self-hosted  # la ramène sur le PC
```

- **Pause** : c'est le geste de l'opérateur (un jeu, par exemple) ; personne
  ne reprend à sa place, et `./bin/factory-doctor` la classe ADVISORY.
- **Runner arrêté** : les PR attendent, `Tests` reste « en file » ;
  `./bin/factory-doctor` le signale ACTIONABLE avec la réparation.
- **`mode github`** dépense des minutes facturées : décision de Benjamin,
  jamais automatique.
- **`install`, `remove`, `broker`** : installation et service ; la moitié
  root est `config/ci-runner/root-install`.
- **Ce que le script ne fait jamais** : afficher, journaliser ou stocker une
  configuration de runner.

Détail : `docs/OPERATIONS.md`, « Factory CI on the host's own runner » ;
frontière de confiance : `docs/SECURITY.md`, même titre.

---
## `./bin/evidence-pack` — où est le dossier que tu juges, et tient-il encore ?

**L'Evidence Pack généré par du code** (Spec af-wf4w5r §10, §9 point 6, T27).
En fin de Spec, tu juges le produit lancé avec une seule page à côté : le
dossier. Du code l'assemble **à partir des pièces enregistrées et de rien
d'autre** ; aucun agent n'en écrit un mot, et la commande ne prend aucun
texte de qui l'appelle. Ne concerne qu'un convoi qui porte la **marque du
nouveau flux**.

```bash
./bin/evidence-pack generate <convoi> --repo <dépôt du projet>   # écrit la page et l'enregistre sur le convoi
./bin/evidence-pack check    <convoi> --repo <dépôt du projet>   # le dossier enregistré tient-il encore ? n'écrit rien
```

- **Où est la page** : `generate` répond `page`, le chemin d'un
  `index.html` sous `~/.local/state/agent-factory-evidence-packs/<spec>/<convoi>/<commit>/`
  (`EVIDENCE_PACK_DIR`). Page statique : elle s'ouvre dans un navigateur,
  sans script, avec ses pièces à côté d'elle.
- **Ce qu'elle porte**, dans l'ordre de la Spec : 1 en-tête (Spec et
  digest, branche, commit, verdict de chaque condition de fin de Spec) ;
  2 **ce qui demande tes yeux** (propositions, écarts de fidélité, captures
  côte à côte et image de différence, remarques d'exploration, mentions
  « même fournisseur ou même modèle que l'auteur ») ; 3 **ce qui n'a PAS été
  vérifié** ; 4 par user story ; 5 par ticket ; 6 éléments suivis ; 7 hors
  graphe initial (repairs, Planning Exceptions, dérogations, tes réponses) ;
  8 relevés (fichiers hors Declared Scope, modèles, durée, tours de fin,
  contradictions) ; 9 preuves TDD et constats de revue.
- **« Ce qui n'a PAS été vérifié » est obligatoire** : états d'écran non
  prototypés lus dans la Spec, critères du socle sans mécanisme et limites
  connues des contrôles lus dans `config/evidence-pack.json`. Si la rubrique
  ne peut pas être remplie, **la génération est refusée** et rien n'est
  écrit.
- **Une condition rouge ne refuse pas la page** : elle est produite avec
  « Dossier non conforme » en en-tête et le verdict de chaque condition.
  C'est le dossier dont le lien accompagne la demande « non conforme »
  (T26) : quand les tours de réparation de fin sont arrêtés,
  `./bin/convoy-advance` le fait générer et t'envoie son chemin
  (`./bin/escalation-door list`). La rubrique 8, « Tours de fin », dit
  alors l'arrêt : sa cause (tours épuisés, tour qui n'a pas réduit les user
  stories non observées, même user story refusée deux fois), le commit,
  l'heure et la précision. La demande elle-même n'y figure pas : elle est
  écrite après la page et porte son lien.
- **Un commit de plus le périme** : `check` répond `à jour`, `absent`,
  `périmé` (un commit de plus, ou un relevé qui a changé depuis), `altéré`
  (page ou pièce réécrite à la main) ou `incomplet` (pièce refusée par le
  magasin de preuves). La porte de fin de Spec lit cette réponse comme sa
  dernière condition et refuse sans dossier complet à jour.
- **Deux générations sur le même état** donnent la même page, octet pour
  octet : elle ne porte aucune heure de génération.
- **Après la fusion d'un Outcome accepté (T30)** : `promoted`, lancé par
  `./bin/outcome-promote`, écrit `fusion.html` dans le dossier du commit
  que tu as jugé — le commit jugé, le commit de fusion, la branche protégée
  avant la fusion, tes mots. `index.html`, la page que tu as jugée, ne
  change pas d'un octet et garde son empreinte.
- **Sorties** : 0 fait, ou dossier à jour ; 1 refus, ou dossier qui ne tient
  pas ; 3 état sans règle ; 4 convoi sans marque.
- **Limites** : les captures côte à côte sont celles du dernier contrôle de
  fidélité de chaque ticket d'écran, à son commit — aucune n'est refaite au
  commit du dossier, et la page le dit ; l'en-tête ne porte pas l'adresse
  d'un produit lancé (rien ne le lance à la génération) ; la rubrique
  « Depuis ton dernier jugement » viendra avec l'enregistrement de
  l'acceptation ; aucun vrai convoi n'a encore de dossier.

Détail : `docs/EVIDENCE_PACK.md`.

---
## `./bin/acceptance-session` — lancer le produit que tu juges, puis l'arrêter

**L'Acceptance Request et l'Acceptance Session** (Spec af-wf4w5r §11, T28).
Quand un convoi qui porte la **marque du nouveau flux** est Delivered,
`./bin/convoy-advance` t'envoie **une** demande : dans
`./bin/escalation-door list`, la ligne
`<convoi> — Acceptance Request — convoi <convoi> : un Delivered Outcome attend votre jugement — dossier : <chemin de la page>`.
Elle porte le lien du dossier, une seule option (« Ouvrir l'Acceptance
Session ») et **aucune recommandation**. Du code, et aucun agent, lance
ensuite le produit que tu juges et l'arrête.

```bash
./bin/acceptance-session open   <convoi> [--repo <dépôt du projet>] [--profile <profil>]   # lance le produit au commit du dossier
./bin/acceptance-session close  <convoi>                                                   # l'arrête, répond une fois chaque port libéré
./bin/acceptance-session record <convoi> --response relancer|planification|abandon         # issue d'une demande « non conforme »
```

- **Comment t'en servir** : ouvre la page du dossier dans un navigateur,
  demande à ta session opérateur d'exécuter `open`, ouvre l'adresse rendue
  (`address`, et `products` : une adresse par jeu de données synthétiques du
  profil), juge, puis `close`.
- **Ce que `open` lance** : le produit depuis une copie propre du commit du
  dossier, par la recette du profil du projet (`./bin/project-launch`), une
  fois par jeu de données déclaré, chacun sur son port — tous, ou aucun.
  Même commande pour le dossier d'un Delivered Outcome et pour celui d'une
  demande « non conforme » (T26) ; dans ce second cas la réponse porte les
  trois `issues`.
- **Refus de `open`** : rien à juger (convoi ni Delivered ni porteur d'une
  demande « non conforme ») ; session déjà ouverte sur ce convoi ; dossier
  qui n'est pas « à jour » selon `./bin/evidence-pack check`, ou qui n'est
  plus celui de la demande (la prochaine passe en génère un nouveau) ;
  aucun profil ou aucune recette de lancement ; profil qui ne nomme aucun
  jeu de données (rien n'est lancé) ; état sans règle.
- **Une panne n'est pas un jugement** : si le produit ne démarre pas, `open`
  le dit (`outage: true`), n'ouvre aucune session et note la panne sur le
  convoi ; la **passe suivante** de `./bin/convoy-advance` publie un
  `repair` qui rétablit le démarrage. Tant que le produit réparé n'a pas son
  propre dossier, `open` à ce commit est refusé et nomme ce `repair`.
- **Ce que l'agent de la session fait et ne fait pas** : `open` lui rend
  ses `rules` avec l'adresse — ouvrir le produit et y naviguer à ta demande,
  rédiger tes constats **avec tes mots**, donner le lien du dossier **sans
  le résumer**, **ne jamais recommander** une réponse ni dire si le produit
  mérite d'être accepté, fermer par `close`.
- **Aucun délai ne répond à ta place** : rien n'accepte, ne fusionne ni ne
  ferme sur une horloge ; un Delivered Outcome le reste jusqu'à ta réponse.
- **`record`** ne vaut que pour une demande « non conforme » : il remet à
  `./bin/escalation-door repondre` l'issue que tu as choisie (relancer un
  tour, retourner à la planification, abandonner). « accepté » y est
  refusé, et rien n'est enregistré.
- **Sorties** : 0 fait ; 1 refus ou panne (`error` commence par
  « refus : ») ; 3 état sans règle ; 4 convoi sans marque.
- **Limites** : tes trois réponses à un Delivered Outcome (accepté,
  constats rendus, abandonné) s'enregistrent par une autre commande,
  `./bin/owner-answer` (T29, `docs/OWNER_ANSWER.md`), et répondre à l'option
  de l'Acceptance Request sur la porte ne déclenche rien ; l'issue d'une
  demande « non conforme » est enregistrée mais rien ne la lit (T29 ne
  traite que le Delivered Outcome) ; le `repair` d'une panne est publié par
  la passe suivante, pas par `open`, et **aucun** n'est publié tant que les
  tours de fin sont arrêtés ; le journal de lancement d'un produit qui ne
  démarre pas n'est pas conservé (une ligne de précision sur la panne) ; le
  relevé de la session est un état local de l'hôte
  (`~/.local/state/agent-factory-acceptance-session`,
  `ACCEPTANCE_SESSION_STATE_DIR`), pas un champ du tracker ; les règles
  sont remises à l'agent, aucun code ne l'empêche de les enfreindre ; aucun
  vrai convoi n'a encore atteint l'acceptation.

Détail : `docs/ACCEPTANCE_SESSION.md`.

---
## `./bin/owner-answer` — enregistrer ta réponse à un Delivered Outcome

**Ta réponse et la route de chaque Owner Finding** (Spec af-wf4w5r §11,
T29). Quand tu as jugé le produit dans l'Acceptance Session
(`./bin/acceptance-session open`), c'est **le seul outil** qui enregistre ce
que tu réponds. Toi seul réponds : `--approved-by` doit être le
`human_approver` de `config/projects/<rig>.toml`. Un refus n'écrit rien.

```bash
./bin/owner-answer verdict <convoi> --proposition <ticket>:out_of_ticket.N --verdict "à faire avant d'accepter"|"plus tard"|"sans suite" --approved-by <toi> --words "<tes mots>"
./bin/owner-answer record  <convoi> --response accepté --approved-by <toi> --words "<tes mots>" --commit <commit du dossier> --pack-digest <empreinte>
./bin/owner-answer record  <convoi> --response "constats rendus" --approved-by <toi> --words "<tes mots>" --commit <commit> --pack-digest <empreinte> --findings <fichier.json>
./bin/owner-answer record  <convoi> --response abandonné --approved-by <toi> --reason "<une ligne>"
./bin/owner-answer resolve-exception <convoi> --approved-by <toi> --words "<tes mots>"
```

- **Comment t'en servir** : tu dis ta réponse à ta session opérateur, avec
  tes mots ; elle lance la commande avec le `commit` et le `digest` que
  `./bin/acceptance-session open` a rendus.
- **D'abord un verdict par proposition** du dossier (rubrique 2) :
  « sans suite » ; « plus tard » (du code crée une proposition par
  `./bin/proposal-door`, elle ne bloque pas) ; « à faire avant d'accepter »
  (bloque « accepté » tant que tu ne l'as pas rendue avec tes constats).
- **« accepté »** porte sur l'Outcome entier, à un commit : tes mots, le
  commit et l'empreinte du dossier. Refusé si le commit n'est pas celui du
  dossier ou n'est plus la pointe de la branche d'intégration, si
  l'empreinte n'est pas la sienne, si le dossier est périmé, si une
  proposition n'a pas de verdict. Cette commande ne ferme et ne fusionne
  rien elle-même : **la passe suivante fusionne et ferme le convoi**
  (`./bin/outcome-promote`), ou annule ton acceptation si la branche
  protégée a bougé et que sa reprise est rouge.
- **« constats rendus »** : un fichier
  `{"findings": [{"text", "cites"?: {"kind", "ref"}, "repair"?: {…}, "later"?: true}]}`.
  **Le code route chaque constat**, pas l'agent : il cite une user story
  que la Spec porte, ou une ancre → un `repair` (rédigé avec le constat,
  obligatoire), publié par la passe suivante de `./bin/convoy-advance` ;
  `later` → une proposition, hors de cet Outcome ; **tout le reste → la
  Planning Exception unique du lot, jamais un `repair`** (tu demandes ce que
  la Spec n'exige pas). L'Outcome n'est plus Delivered, la demande quitte ta
  liste, les tours de fin repartent de zéro ; une fois les `repair` livrés,
  toute la porte de fin de Spec repasse et un **nouveau dossier** arrive,
  qui s'ouvre sur la rubrique 0 « Depuis ton dernier jugement ».
- **« abandonné »** exige une raison d'une ligne ; la passe suivante ferme
  le convoi avec elle, sans rien fusionner.
- **« refusé » n'est pas une réponse**, et il n'y a **aucune acceptation
  partielle** : les deux sont refusés avec la raison.
- **Rien ne rouvre** un Outcome accepté ou abandonné : un défaut ou un
  souhait trouvé après entre comme travail nouveau, par un Planning Run.
- **`resolve-exception`** : tu dis que la Planning Exception du lot est
  résolue, une fois la Spec amendée approuvée (`bin/spec-approve`, qui
  approuve de nouveau une Spec dont le texte a changé) et le graphe révisé
  publié (`bin/ticket-graph-publish bd-patch`) ; sinon refus, qui dit
  l'étape qui manque ; d'ici là la fin de Spec attend.
- **Cockpit** : sur un convoi du nouveau flux, le bouton « Accepter » est
  refusé et renvoie ici ; l'étape « Accepté » se lit dans ta réponse
  enregistrée.
- **Sorties** : 0 fait ; 1 refus (`error` commence par « refus : », état
  sans règle compris) ; 4 convoi sans marque.
- **Limites** : entre ta réponse et la passe qui la suit, l'Outcome est
  accepté et pas encore fusionné ; un « plus tard » dont la proposition
  n'était pas encore créée à ce moment n'est plus relancé par la passe ; la
  Planning Exception du lot est enregistrée et
  retient la fin de Spec, mais le Planning Run qui amende la Spec se fait à
  la main — aucun code ne le lance, rien ne prévient le Mayor, et
  `resolve-exception` te croit sur parole ; l'issue d'une demande
  « non conforme » n'est toujours lue par rien (seul « abandonné »
  s'enregistre sur ce dossier) ; rien n'empêche techniquement un agent
  d'inventer tes mots ou de passer ton nom — le relevé le rend visible
  après coup ; une citation `anchor` n'est pas vérifiée contre le Validated
  Prototype ; le routage lit la citation, pas le sens — un constat qui cite
  une story existante en demandant plus est routé en `repair` ; si la porte
  des propositions échoue après l'écriture, la réponse est enregistrée et
  la proposition manque ; aucun vrai convoi n'a encore reçu de réponse.

Détail : `docs/OWNER_ANSWER.md`.

---
## `./bin/outcome-promote` — ce que le code fait une fois que tu as répondu « accepté » ou « abandonné »

**La fusion unique et la fermeture du convoi** (Spec af-wf4w5r §9 et §11,
T30). Tu n'as **rien à lancer** : dès que ta réponse est enregistrée par
`./bin/owner-answer`, la passe suivante de `./bin/convoy-advance` lance
cette commande. Aucun agent ne peut la lancer : `run` est refusé à toute
session d'agent.

```bash
./bin/outcome-promote check <convoi>   # ce que run ferait : merge, close ou nothing ; n'écrit rien
./bin/outcome-promote run   <convoi>   # ce que l'ordre de l'usine lance ; refusé à une session d'agent
```

- **Avant « accepté »**, rien du convoi n'est dans la branche protégée :
  tout est sur la branche d'intégration.
- **« accepté »** : la branche d'intégration est fusionnée dans la branche
  protégée par **un seul commit de fusion**. Le relevé garde les deux
  commits — celui que tu as jugé et celui de la fusion
  (`./bin/convoy-state show`, `promotion`) — et une page `fusion.html` les
  note à côté du dossier que tu as jugé, qui ne change pas d'un octet. Les
  preuves de la Spec sont purgées, le convoi est fermé sur tes mots, sa
  Spec et son brouillon de graphe sont fermés.
- **Si la branche protégée a bougé depuis ton jugement**, le code la
  reprend d'abord dans la branche d'intégration et rejoue **seulement les
  contrôles mécaniques** : commande de régression, fidélité au Validated
  Prototype, démarrage du produit. Verts : la fusion se fait, et le relevé
  dit que la pointe fusionnée est ton commit plus cette reprise.
- **Rouges, ou les deux branches sont en conflit** : **rien n'est
  fusionné** et **ton acceptation est annulée** (elle reste au relevé, avec
  la cause). Un `repair` est publié, puis toute la porte de fin de Spec
  repasse et tu reçois une **nouvelle Acceptance Request** : tu juges de
  nouveau.
- **« abandonné »** : rien n'est fusionné ; le convoi est fermé avec ta
  raison ; la branche d'intégration reste où elle est, comme source.
- **Rien ne rouvre** un convoi fermé ainsi, ni lui ni ses tickets : toute
  écriture y est refusée. Un défaut ou un souhait trouvé après entre comme
  travail nouveau, par un Planning Run.
- **Un convoi fermé autrement** (à la main), même avec ta réponse, reste un
  « état sans règle » signalé sur ta liste.
- **Sorties** : 0 fait, ou rien à faire ; 1 refus, ou rouge (`error`
  commence par « refus : », `red` nomme le contrôle) ; 3 état sans règle ;
  4 convoi sans marque.
- **Limites** : sur un dépôt avec remote, la fusion est une **poussée
  directe** vers la branche protégée (gardée par un bail sur sa pointe),
  pas une pull request — si une protection de branche la refuse, l'Outcome
  reste accepté et non fusionné, chaque passe réessaie et le dit, rien
  d'autre ne te prévient ; sans remote, un répertoire de travail qui a la
  branche protégée extraite n'est pas rafraîchi ; **rien ne te prévient
  qu'une acceptation est annulée**, tu reçois seulement la nouvelle demande
  après le `repair` ; un rejeu coupé par le délai de l'ordre après la
  reprise fusionne à la passe suivante sans rejouer la fidélité ni le
  démarrage ; les dossiers ne sont jamais purgés ; aucun vrai convoi n'a
  encore été fusionné ainsi.

Détail : `docs/OUTCOME_PROMOTE.md`.

---
## `./bin/method-check` — chaque exigence a-t-elle son mécanisme, chaque écart sa raison ?

**Deux contrôles en lecture seule sur ce que l'usine dit de sa propre
méthode** (D01 T31, Spec af-wf4w5r §9 et §16). Ils tournent à chaque run de
la CI de l'usine par `tests/method-check-test.py` : une pull request qui
casse l'un des deux est rouge.

```bash
./bin/method-check table      # docs/REQUIREMENT_TABLE.md
./bin/method-check register   # docs/ADAPTATION_REGISTER.md
```

- **`table`** : la table exigence → mécanisme → preuve. Rouge, en nommant la
  ligne, si un mécanisme est vide, ne nomme aucune commande (`bin/<nom>`),
  nomme une commande qui n'est pas un fichier exécutable de `bin/`, ou si la
  preuve est vide. Renommer une commande citée rend donc sa ligne rouge.
- **`register`** : l'Adaptation Register. Rouge si une entrée `AR-NNN` n'a
  pas de raison (champ `But`), si un écart de la liste « Écarts de la Spec
  D01 » ne nomme aucune entrée, nomme une entrée absente, ou une entrée dont
  le champ `Baseline` ne nomme pas la base de comparaison v1.3.1.
- **Sorties** : 0, une ligne ; 1, une raison en français par ligne sur
  stderr, chacune avec sa ligne ou son entrée ; 2, usage. `--root <dossier>`
  fait lire un autre arbre (les tests l'emploient sur une copie).
- **Limites** : le contrôle lit des noms et des champs, pas le fond. Il ne
  prouve ni qu'une commande tient l'exigence de sa ligne, ni qu'une raison
  est bonne, ni que la liste des écarts est celle de la Spec : la liste des
  lignes de la Spec §9 et des écarts de la Spec §16 est tenue par le test.

Détail : `docs/REQUIREMENT_TABLE.md`, `docs/ADAPTATION_REGISTER.md`.

---
## `./bin/test-cases-compare` — mêmes cas, mêmes vérifications, avant et après ?

**La preuve d'un fichier de test accéléré ou descendu d'un étage** (CI01,
Spec af-q9urgr §1) : le nom de chaque cas et son nombre de vérifications,
comparés entre deux états du fichier. Rien n'est lancé ni écrit : les
sources sont seulement lues.

```bash
./bin/test-cases-compare --before origin/main:tests/x-test.py --after tests/x-test.py
# un fichier coupé en deux : --after deux fois
./bin/test-cases-compare --before origin/main:tests/x-test.py --after tests/x-test.py --after tests/x-suite-test.py
```

- **Source** : un fichier, ou `RÉVISION:chemin` lu par `git show` depuis le
  dossier courant. Plusieurs sources d'un même côté sont lues comme un seul
  ensemble de cas.
- **Cas** : une méthode `test*` d'une classe du fichier, nommée
  `Classe.méthode`, méthodes héritées d'une classe du même fichier comprises.
  Ce qui tourne autour des cas est comparé de la même façon sous son nom
  (`Classe.setUp`, `setUpClass`, `tearDown`, `tearDownClass`).
- **Vérifications** : les `assert`, et les appels d'une méthode `assert*` ou
  `fail`, dans le corps du cas et dans chaque aide du même fichier qu'il
  nomme (méthodes par `self`, `cls` ou `super()`, fonctions du module). Une
  aide qui perd une vérification fait donc baisser chaque cas qui s'en sert.
- **Sorties** : 0, une ligne (`N cas, V vérifications avant, V après sur les
  mêmes cas : identiques`, ou `aucun cas ni vérification en moins` s'il y en
  a en plus), puis une ligne par cas nouveau, par cas qui a des vérifications
  en plus, et une pour les cas sans vérification comptée ; 1, une raison en
  français par ligne sur stderr, chacune avec son cas : cas disparu, cas
  renommé, vérifications en moins, cas qui ne tournerait plus comme avant
  (bases de sa classe changées, décorateur ou `skipTest` ajouté), cas
  présent deux fois ; 2, usage, source illisible, ou aucun cas avant.
- **Où sa sortie va** : dans la pull request qui accélère le fichier, avec
  les secondes avant et après.
- **Limites** : les vérifications sont comptées, pas exécutées. Le contrôle
  ne lit pas ce qu'une vérification vérifie, ni si elle est atteinte (code
  après un `return`, sous `if False`, décorateur qui n'appelle pas ce qu'il
  enveloppe, cas retiré par une affectation `test_x = None`, fonction
  `test*` hors d'une classe) ; ce qu'un cas atteint dans un autre module
  n'est pas suivi, y compris l'autre moitié d'un fichier coupé en deux ;
  seuls les fichiers Python sont lus. Il ne voit pas un décor partagé qui
  fuit d'un cas à l'autre : cela se relit, et se rejoue dans l'ordre inverse.

Tests : `tests/test-cases-compare-test.py`.

---
## `./bin/ci-test-ceiling` — un fichier de test dépasse-t-il 120 secondes ?

**Le plafond de durée par fichier de test, tenu par du code** (Spec CI01,
af-q9urgr §3 ; la règle est `docs/TEST_GUIDELINE.md`, point 5). Il lit les
durées que la CI enregistre déjà (`config/ci-test-seconds.tsv`) et ne mesure
rien. Il tourne à chaque run de la CI de l'usine par
`tests/ci-test-ceiling-test.py` : une pull request qui enregistre un fichier
au-dessus du plafond est rouge.

```bash
./bin/ci-test-ceiling check   # lecture seule
./bin/ci-test-ceiling prune   # retire de la liste connue les fichiers repassés sous le plafond
```

- **Rouge**, en nommant le fichier : un fichier de test au-dessus de 120 s ;
  une exception écrite sans raison ; une ligne ajoutée à la liste connue ;
  une ligne de la liste dont le fichier n'est plus au-dessus de 120 s.
- **Exception écrite** : une ligne du fichier de test,
  `# ci: over-ceiling — <raison>`. Le modèle laissé tel quel ou une raison
  de moins de 10 caractères est refusé.
- **Durées illisibles** : fichier absent, sans aucune durée, ou portant une
  ligne qui n'est ni un commentaire ni `<chemin><TAB><secondes>` : rouge, en
  nommant la ligne. `prune` ne touche alors pas à la liste.
- **Liste connue** : `config/ci-test-ceiling-known.txt`, les 20 fichiers
  déjà au-dessus à la mise en place (2026-10-10). Elle ne peut que rétrécir :
  la commande porte elle-même les 20 noms de ce jour-là et refuse tout autre
  nom dans la liste.
- **Quand ça rougit** : seulement dans la pull request qui change les durées
  enregistrées ou la liste, donc celle qui rafraîchit les durées
  (`./bin/ci-test-seconds`, puis `./bin/ci-test-ceiling prune`). Un fichier
  devenu plus rapide ou plus lent ne rend rouge aucune autre pull request.
- **Sorties** : 0, une ligne ; 1, une raison par ligne sur stderr, chacune
  avec son fichier ; 2, usage. `--root <dossier>` fait lire un autre arbre
  (les tests l'emploient sur un arbre fabriqué).
- **Limites** : un fichier jamais mesuré par la CI n'a pas de plafond avant
  le rafraîchissement suivant ; les durées bougent avec la charge de l'hôte ;
  la qualité d'une raison n'est pas jugée par la commande.

Détail : `docs/TEST_GUIDELINE.md`.

---
## `./bin/convoy-graph` — où en est le convoi d'une Spec ?

**La forme vivante du convoi d'une Spec, en lecture seule.** Il répond à ce
qu'un opérateur demande d'un convoi qui tourne, d'une lecture du tracker et
d'une des sessions : les sessions réellement actives, les tickets prêts à
démarrer, le chemin critique du travail restant et la largeur par niveau.

```bash
./bin/convoy-graph af-2zseit          # texte
./bin/convoy-graph af-2zseit --json   # un objet JSON
```

- **Sessions** : `gc session list`, pas `gc status`. `gc status` affiche
  « stopped » pour un emplacement de pool alors que des sessions de son
  modèle tournent ; un agent en a conclu à tort « agents arrêtés »
  (2026-10-15). Chaque session active nomme le ticket qu'elle porte.
- **Dépendances** : `gc.blocked_by` de chaque ticket (clés de ticket). Un
  bloqueur livré ou retiré ne retient plus ; une clé qu'aucun ticket de la
  Spec ne porte retient, et elle est nommée.
- **Prêt** : ouvert, non retiré, jamais démarré (ni porte `dispatch` ni
  sortie), plus rien à attendre — la frontière d'où part
  `bin/convoy-advance`, avant son plafond de sessions.
- **Chemin critique et niveaux** : ceux du travail restant (ni fermé ni
  retiré), calculés par `lib/ticket_graph.py`, le code de la borne de chemin
  critique de la relecture de graphe (ADR-0031). Niveau 1 : n'attend rien ;
  la largeur d'un niveau dit combien d'auteurs il peut occuper à la fois.
- **Sorties** : 0 ; 1 si le tracker ou les sessions ne se lisent pas, ou si
  aucun ticket ne porte la Spec ; 2, usage. N'écrit rien.
- **Limites** : un instantané, pas une surveillance ; le plafond N de
  `bin/convoy-advance` et ses arrêts (rouge d'intégration, Planning
  Exceptions) ne sont pas appliqués ici : `docs/CONVOY_ADVANCE.md`.

Preuve : `tests/convoy-graph-test.py`.
