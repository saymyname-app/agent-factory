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
| `config-invariants` | `permission_mode` est sain et les 5 providers vérifiés (`codex`, `codex-readonly`, `claude`, `claude-readonly`, `claude-standard`) résolvent |
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

