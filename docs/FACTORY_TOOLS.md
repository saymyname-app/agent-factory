# Outils d'usine — ce qu'ils font, quand les lancer

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
| `config-invariants` | `permission_mode` est sain et les 5 providers résolvent |
| `work-backup` | **pousse** toute branche qui n'existe que sur cette machine |
| `work-tree` | **sauvegarde** l'arbre de travail modifié ou non suivi (voir plus bas) |
| `rig:*` | un rig suspendu bloque la livraison ; un dispatcher au repos, non |
| `worktrees` | nomme les worktrees qui épinglent encore une branche fusionnée |
| `provider overlay` | **régénère** `city.provider.toml` s'il a disparu (sans lui, la config de la cité ne charge plus) |
| `pii-guard` | (af-6eqc) signale — sans jamais l'afficher — si un identifiant réel de `.gc/pii-guard/real-identifiers.local` apparaît dans le diff sortant ou l'arbre de travail ; le blocage réel se fait dans `.githooks/pre-push` via `./bin/factory-pii-guard` |
| `liveness` | vérifie que la campagne **avance**, pas seulement que les pièces répondent ; ouvre **un** signalement pour le Mayor si elle stagne, et le lui envoie par mail (`--notify`) au moment du dépôt — `./bin/factory-watchdog` relance ensuite tant qu'il reste ouvert |

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

### La vivacité, en clair

Un contrôle de santé répond à « les pièces sont-elles là ». La vivacité répond à
« quelque chose a-t-il bougé ». La nuit du 2026-09-15, tout était vert pendant
six heures d'immobilité.

La sentinelle de campagne laisse deux horodatages sur le bead de coordination :
`gc.campaign_sentinel_at` (la boucle a tourné) et `gc.campaign_progress_at`
(quelque chose a avancé : livraison en cours, bead Factory en cours, ou
**nouveau** réveil envoyé au Mayor). Le garde-fou alerte si :

- la boucle est muette depuis **10 min** ;
- la campagne vit mais n'avance plus depuis **60 min** (réglable :
  `FACTORY_LIVENESS_MINUTES`).

Une pause volontaire (fenêtre de maintenance, quotas épuisés) est affichée,
jamais signalée comme panne. Les règles sont dans `lib/factory_liveness.py`.

---

## `./bin/factory-watchdog` — la surveillance qui page, pas seulement qui observe

La vivacité de `factory-guard` répond à « la campagne avance-t-elle ». Trois
autres signaux peuvent rester muets même quand elle avance
(`INCIDENT_2026-09-16-silent-campaign-stall.md`) :

```bash
./bin/factory-watchdog                # par défaut : vérifie ET page (mail + bead)
./bin/factory-watchdog --check-only   # ne touche à rien, sort non-zéro si problème
```

| Contrôle | Ce qu'il fait |
|---|---|
| `gates` | une « Gate: human » ouverte depuis plus de 30 min (réglable) est re-signalée au Mayor, pas seulement laissée dans la file |
| `prs` | une PR du dépôt Factory en `CONFLICTING`, ou dont aucun contrôle CI n'a jamais démarré, après 30 min — distincte d'une PR qui attend simplement son tour |
| `workflows` | un bead molécule/workflow fermé `CLOSED` avec `gc.outcome` ≠ `pass` (le cas `on_fail=abort_scope` : chaque étape en aval passe `outcome=skipped` en silence) |
| `liveness` (relais) | re-signale un défaut de vivacité déjà déposé par `factory-guard` tant qu'il reste ouvert, au lieu de le laisser filer une seule fois |

**Observe et page seulement** (ADR-0016 §7) : il ne résout jamais une porte,
ne fusionne ni ne ferme jamais une PR, et ne rouvre jamais un workflow. Chaque
signalement devient au plus un mail au Mayor (`gc mail send mayor --notify`,
relancé sur un délai de repli, jamais à chaque passage) et, pour les portes et
PR, un bead qui survit au passage suivant. Les règles pures sont dans
`lib/factory_watchdog.py` ; les décisions déterministes sont dans
`lib/factory_liveness.py` pour la vivacité elle-même.

Les signalements sont aussi écrits dans
`.gc/runtime/factory-watchdog-signals.json`, que le panneau « Aujourd'hui » du
cockpit lit de façon additive (`today.watchdog_alerts`) — sans jamais
modifier `human_state.campaign.blocked` : un signalement local ne doit
jamais se lire comme un arrêt de toute la campagne.

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

## `./bin/mayor-campaign` — l'état canonique de la campagne

La campagne est la boucle qui enchaîne les résultats produit sans intervention
humaine (ADR-0013, ADR-0016).

```bash
./bin/mayor-campaign status        # lecture seule, canonique
./bin/mayor-campaign sentinel      # la sentinelle de réveil, zéro token
./bin/mayor-campaign block --mayor --kind <k> --owner <o> --cause ... --action ...
./bin/mayor-campaign resume --mayor
```

**À lire en premier dans toute nouvelle session.** Un `ERROR` sur `status`
signifie que la boucle de réveil est **morte**, pas qu'elle se repose — la
distinction est exactement ce qui a coûté une nuit le 2026-09-15.

Les transitions exigent le garde `--mayor`. C'est un garde « transition
délibérée », **pas** une revendication d'identité : déclarez l'auteur réel dans
`--cause`. Le Mayor lit ce champ et peut prendre une recommandation du PO pour
une décision de Benjamin.

### Ce que fait la sentinelle quand il n'y a pas de travail produit

Rien de produit à faire n'est pas de l'inactivité (ADR-0016 §7). La sentinelle
descend l'**échelle d'inactivité** :

1. travail produit (inchangé) ;
2. un bead Factory prêt dans le store de la cité, le plus prioritaire, **un à la fois** ;
2b. un candidat éligible de la file `goal=none` (`saymyname-product-queue`) ;
3. durcissement des tests et chasse aux tests instables — au plus toutes les 12 h ;
4. ménage du backlog et dette documentaire — au plus toutes les 24 h ;
5. **un axe d'amélioration nommé** (`config/factory-improvement-axes.json`,
   `FACTORY_CONTINUITY.md` §4) — au plus toutes les 6 h, et seulement si le
   commutateur maître **« maintenir en vie »** est actif (par défaut : oui) ;

puis se repose. Ne sont jamais proposés : sessions, nudges, convois, étapes
internes, objectifs produit, beads étiquetés `upstream`, beads tenus par
quelqu'un d'autre, beads qui attendent Benjamin ou qui portent
`gc.waiting_on=<qui>` (c'est ainsi qu'un agent fait sauter un bead à l'échelle).

Le commutateur « maintenir en vie » (`./bin/factory-improvement-axes`, section
suivante) coupe **tout l'échelon au-delà d'un bead déjà en cours** — pas
seulement l'échelon 5 — et rend la sentinelle explicitement silencieuse
(`maintain_alive_off`, visible dans le cockpit) au lieu de laisser croire à un
blocage. Un axe marqué `draft_only` (ex. `auth-providers`) ne matérialise
jamais de travail exécutable, seulement un bead de proposition en attente
d'acceptation humaine.

Une décision produit en attente ne met en pause **que** le travail produit :
l'échelle continue. Une fenêtre `admin`, une limite de fournisseurs ou une panne
durable, elles, font taire la sentinelle.

### Un réveil qui n'a rien donné est renvoyé

Un réveil marqué « envoyé » l'était pour toujours. Le 2026-09-16, un simple
redémarrage a suffi : la nouvelle session du Mayor ne savait plus rien, et la
sentinelle ne le lui redisait jamais. Désormais, un réveil sans progrès est
renvoyé au bout de **30 min**, marqué `RAPPEL n/3`, **trois fois au plus**.
Ensuite, c'est la vivacité qui ouvre un signalement. Les échelons 3 et 4,
facultatifs par nature, ne sont jamais relancés.

Au passage qui suit un échec transitoire, la sentinelle ne fait rien : l'état qu'elle vient de lire était masqué par cet échec. Elle agit au passage suivant.

`--kind admin` est le type prévu pour une fenêtre de maintenance. Depuis le
2026-09-16, un blocage `admin` enregistré survit à l'arrêt du contrôleur au lieu
d'être écrasé par un diagnostic de panne.

---

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

**Depuis le cockpit** (ordinateur : « Aujourd'hui » › Fournisseurs IA ;
téléphone : écran État) :

| Réglage | Effet |
|---|---|
| Marquer épuisé (durée ou date) | pour une limite que l'usine n'a pas vue |
| Rétablir | le quota est de nouveau utilisable |
| Désactiver / Réactiver | exclut un fournisseur de toutes les chaînes |
| ↑ / ↓ | change l'ordre de repli d'une cible |
| Forcer | impose un fournisseur à une cible, même épuisé |
| Repli automatique (case) | désactivé : les limites détectées sont affichées mais plus appliquées |

Tout est réversible et ne consomme aucun token.

**En ligne de commande** :

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
| `.gc/provider-state.json` | limites détectées, réglages du cockpit, historique | non |
| `city.provider.toml` | surcouche **générée**, incluse par `city.toml` | non |

**Ne jamais éditer `city.provider.toml` à la main**, ni le fournisseur dans
`city.toml` (ce n'est plus qu'une valeur de secours). **Ne jamais supprimer**
`city.provider.toml` : sans lui la config ne charge plus — le garde-fou le
régénère, mais autant ne pas lui en donner l'occasion.

Un quota s'applique à un **pool** : les trois profils Claude partagent le même
compte, donc une limite Claude les épuise tous. Codex standard et Codex Spark
sont deux pools distincts.

Si **aucun** fournisseur ne reste pour les ouvriers, la campagne est mise en
pause (`limit`, cause `[provider-failover]`) avec l'heure de reprise la plus
proche, puis **reprise automatiquement**. Cela ne demande jamais Benjamin.

La tâche planifiée `provider-failover` tourne toutes les 2 min (~1 s, < 1 s de
CPU : les écrans sont lus via tmux, pas via `gc session peek` qui coûtait 8 s).

---

## `./bin/factory-improvement-axes` — les axes d'amélioration et « maintenir en vie »

L'échelon 5 de l'échelle d'inactivité (`mayor-campaign` ci-dessus,
`FACTORY_CONTINUITY.md` §1/§4, ADR-0016 §7) : quand la file de release n'a
plus rien d'éligible, l'usine avance sur un **axe nommé et borné** plutôt que
de s'arrêter.

**Depuis le cockpit** (ordinateur : « Aujourd'hui » › Axes d'amélioration) :

| Réglage | Effet |
|---|---|
| Maintenir en vie (case) | désactivé : l'échelle s'arrête entièrement au-delà d'un bead déjà en cours, et le dit explicitement |
| Case par axe | active/désactive cet axe seul, sans toucher aux autres |

Tout est réversible et ne consomme aucun token.

**En ligne de commande** :

```bash
./bin/factory-improvement-axes status --json
./bin/factory-improvement-axes set --action maintain-alive --args '{"enabled":false}'
./bin/factory-improvement-axes set --action enable  --args '{"axis":"security"}'
./bin/factory-improvement-axes set --action disable --args '{"axis":"i18n"}'
```

Deux fichiers, un seul écrivain, même partition que `provider-failover` :

| Fichier | Rôle | Versionné |
|---|---|---|
| `config/factory-improvement-axes.json` | axes nommés, périmètre, `draft_only`, défauts | oui |
| `.gc/runtime/factory-improvement-axes-state.json` | activé/désactivé courant, historique | non |

Un axe `draft_only` (ex. `auth-providers` : ajouter un fournisseur de
connexion est une décision de classe réservée, ADR-0015 §3) ne matérialise
**jamais** de travail exécutable — seulement un bead de proposition en
attente d'acceptation humaine. Un axe activé dont le mécanisme n'est pas
encore outillé (ex. `dead-code`) est sauté en silence, comme un échelon
générique vide — ce n'est pas un blocage.

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
