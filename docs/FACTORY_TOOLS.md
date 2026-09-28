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
| `config-invariants` | `permission_mode` est sain et les 4 providers vérifiés (`codex`, `claude`, `claude-standard`, `claude-cheap`) résolvent |
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
