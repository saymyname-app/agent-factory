# Outils d'usine — ce qu'ils font, quand les lancer

> Systèmes retirés (Cockpit V1, ntfy, campagne, file/statut/preview produit,
> contrat de release, axes d'amélioration) : documentés seulement dans
> `../legacy/` (non fiable, voir `../legacy/README.md`).

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
| `config-invariants` | `permission_mode` est sain et les 5 providers vérifiés (`codex`, `claude`, `claude-readonly`, `claude-standard`, `claude-cheap`) résolvent |
| `work-backup` | **pousse** toute branche qui n'existe que sur cette machine |
| `work-tree` | **sauvegarde** l'arbre de travail modifié ou non suivi (voir plus bas) |
| `rig:*` | un rig suspendu bloque la livraison ; un dispatcher au repos, non |
| `build-gates` | (af-uxz57) lit, rig par rig, le catalogue de formules réellement résolu, déduplique leurs contrôles `exec`, puis vérifie que chaque chemin existe et est exécutable dans le rig concerné. Gas City refuse un lien symbolique `exec` sortant du confinement du rig : `bin/factory-build-gates` crée donc des copies régulières pour les contrôles et garde le validateur Python comme dépendance liée au pack afin qu'il résolve ses schémas voisins. Tous ces artefacts sont suivis par `.gc/scripts/.factory-build-gates.json` et actualisés depuis le pack épinglé pour ce rig ; `--check-only` nomme une seule fois chaque couple rig/chemin manquant ou périmé sans écrire. Le démarrage l'exécute avant le contrôleur, et le garde le répare ensuite après un re-clone de rig ou un re-pin du pack. Il ne crée jamais de faux script « toujours vrai » et refuse d'écraser un fichier propre au rig ou un artefact géré modifié hors de l'outil. |
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

Pour récupérer un instantané :

```bash
git fetch origin 'refs/factory-guard/snapshots/*:refs/remotes/snapshots/*'
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
(`../legacy/docs/INCIDENT_2026-09-16-silent-campaign-stall.md`, af-539b0) :

```bash
./bin/factory-watchdog                # par défaut : vérifie ET page (mail + bead)
./bin/factory-watchdog --check-only   # ne touche à rien, sort non-zéro si problème
```

| Contrôle | Ce qu'il fait |
|---|---|
| `gates` | une « Gate: human » ouverte depuis plus de 30 min (réglable) est re-signalée au Mayor, pas seulement laissée dans la file |
| `prs` | une PR du dépôt Factory en `CONFLICTING`, ou dont aucun contrôle CI n'a jamais démarré, après 30 min — distincte d'une PR qui attend simplement son tour |
| `workflows` | un bead molécule/workflow fermé `CLOSED` avec `gc.outcome` ≠ `pass` (le cas `on_fail=abort_scope` : chaque étape en aval passe `outcome=skipped` en silence) |
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
Détails et règles : `../legacy/docs/decisions/ADR-0018-automatic-provider-failover.md`.

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
le Mayor n'est réveillé que si `mergedAt` date d'au plus une heure, ou si un
bead encore `open`/`in_progress` attend réellement ce travail (`blocks` ou
`gc.waiting_on`). Le message unique part de l'identité explicite
`pr-autopilot`, jamais de `human`; un passage ultérieur voit `merge_result` et
ne le renvoie pas. La fenêtre peut être ajustée par
`PR_AUTOPILOT_RECONCILE_WAKE_WINDOW_SECONDS` pour l'exploitation ou les tests.

Ainsi, le rattrapage complète les preuves sans réveiller le Mayor pour des
fusions anciennes, tandis qu'une livraison récente ou bloquante réveille le
Mayor immédiatement.

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
| relecteur | `delivery-reviewer` | `code-review` (masque celui de Claude Code) | oui |
| Evaluator | `delivery-evaluator` | aucun | oui |

Ce qu'une session reçoit vraiment dépend de Gas City et du CLI du
fournisseur : cela ne se lit pas dans un fichier, cela s'essaie. `run` monte
une **cité isolée** (son propre `GC_HOME`, son port de superviseur, jamais la
cité live), ouvre une session réelle par rôle et par fournisseur déclaré, et
relève : les skills chargés (lus dans le transcript de la session), l'empreinte
du `code-review` chargé par le relecteur, le résultat d'une demande de revue
faite à un rôle qui n'en a pas le skill, et le résultat d'une demande d'écrire,
de committer et de pousser faite à un rôle en lecture seule.

```bash
./bin/role-adoption-trial status                # chaque rôle × fournisseur déclaré : essai valide ou non
./bin/role-adoption-trial run                   # essai réel (~1 min par rôle, consomme du quota), écrit le relevé
./bin/role-adoption-trial run --role reviewer   # un seul rôle
./bin/role-adoption-trial verify-distribution   # les copies par rôle = la distribution, octet pour octet
```

- **Relevé** : `config/role-adoption-trials.json`, versionné. Il se committe par
  PR depuis un worktree ; ne jamais l'éditer à la main, relancer l'essai.
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
- **Plafond N** : `max_sessions` dans `config/delivery-flow.json`, un seul
  réglage pour toute l'usine, partagé entre les Specs. Comptent : chaque session
  vivante d'un rôle de livraison (auteur, relecteur, Evaluator) et chaque ticket
  démarré qu'aucune session n'a encore pris.
- **Formule de démarrage** : `start.formula` dans le même fichier. Tant qu'elle
  vaut `null`, la commande refuse de démarrer quoi que ce soit (sortie 1).
- **Sorties** : 0 passe faite ; 1 refus (réglage, tracker, porte de dispatch
  qui refuse un ticket, nommé sous `refused`, ou incident impossible à lever) ;
  3 « état sans règle » : rien n'est démarré dans ce convoi ; 4 « pas un convoi
  du nouveau flux ».
- **Convoi arrêté (« état sans règle »)** : un ticket démarré ou fermé hors de
  sa porte, une preuve sans empreinte, un compteur incohérent. La passe ne
  démarre plus rien dans ce convoi et lève **un seul** incident d'usine : la
  ligne « Incident d'usine : <ticket> — <raison> » apparaît dans
  `./bin/escalation-door list`. Réparer, c'est remettre le tracker dans un état
  valide (`./bin/convoy-state show <convoi>` dit ce qui cloche), **jamais**
  avancer ou fermer un ticket à la main. Dès que l'état est valide, la passe
  suivante reprend le convoi, retire l'incident et ferme son bead toute seule.
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
  refusé et nommé.
- **Critère déjà vert** : le ticket est arrêté (sortie 5), le critère est
  nommé, l'arrêt est écrit dans le tracker.
- **Gel** : les empreintes des tests, de la table et du harnais vont dans le
  magasin de preuves, hors de tout dépôt Git.
- **Vert** : refus si un fichier gelé a été modifié, supprimé ou déplacé ;
  sinon les tests gelés passent k fois de suite. Un résultat mixte nomme le
  test instable.
- **Amendement** : le seul moyen de changer un test gelé, une fois par
  ticket, avec sa raison ; nouveau rouge, nouveau gel, diff enregistré. Le
  second arrête le ticket (sortie 5).
- **Prefactoring** : pas d'étape rouge ; la commande de régression passe
  avant et après ; aucun test existant n'est modifié.
- **Sorties** : 0 étape prouvée ; 1 refus, rien n'est écrit ; 4 « pas un
  convoi du nouveau flux » ; 5 ticket arrêté.
- **Limite** : le script prouve l'ordre et les résultats, pas qu'un test
  observe bien son critère (c'est la question du relecteur de tests). Lever
  un arrêt n'est pas dans cette commande.

Détail : `docs/TDD_STEP.md`.

---

