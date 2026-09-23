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
| `build-gates` | (af-uxz57) lit, rig par rig, le catalogue de formules réellement résolu, déduplique leurs contrôles `exec`, puis vérifie que chaque chemin existe et est exécutable dans le rig concerné. Gas City refuse un lien symbolique `exec` sortant du confinement du rig : `bin/factory-build-gates` crée donc des copies régulières pour les contrôles et garde le validateur Python comme dépendance liée au pack afin qu'il résolve ses schémas voisins. Tous ces artefacts sont suivis par `.gc/scripts/.factory-build-gates.json` et actualisés depuis le pack épinglé pour ce rig ; `--check-only` nomme une seule fois chaque couple rig/chemin manquant ou périmé sans écrire. Le démarrage l'exécute avant le contrôleur, et le garde le répare ensuite après un re-clone de rig ou un re-pin du pack. Il ne crée jamais de faux script « toujours vrai » et refuse d'écraser un fichier propre au rig ou un artefact géré modifié hors de l'outil. |
| `worktrees` | nomme les worktrees qui épinglent encore une branche fusionnée |
| `provider overlay` | **régénère** `city.provider.toml` s'il a disparu (sans lui, la config de la cité ne charge plus) |
| `pii-guard` | (af-6eqc) signale — sans jamais l'afficher — si un identifiant réel de `.gc/pii-guard/real-identifiers.local` apparaît dans le diff sortant ou l'arbre de travail ; le blocage réel se fait dans `.githooks/pre-push` via `./bin/factory-pii-guard`. Sans liste locale (toute machine hors accès dev-DB), le contrôle est INACTIVE — signalé avec `·`, jamais `✓` — et non « propre » : une liste absente ne veut rien dire sur ce qui a été vérifié (voir `DELIVERY.md`, Real-PII leak guard, af-ox44d). `./bin/factory-provenance-guard` (Layer B, CI) ne couvre que les fichiers de données texte (`.json .csv .sql .yaml .yml .xml .properties .tsv`) sous un chemin fixture/seed/test-resource — aucun format binaire (photo, PDF, …) n'est vu par l'une ou l'autre couche |
| `liveness` | vérifie que la campagne **avance**, pas seulement que les pièces répondent ; ouvre **un** signalement pour le Mayor si elle stagne, et le lui envoie par mail (`--notify`) au moment du dépôt — `./bin/factory-watchdog` relance ensuite tant qu'il reste ouvert |
| `session-boot` | (af-jj9u7) distinct de `liveness` : vérifie qu'une session nommée toujours-active (`configured_named_mode = "always"`, ex. le Mayor) peut **démarrer**, pas que la campagne avance — un orchestrateur bloqué en `creating`/`failed-create` plus de 15 min (`FACTORY_SESSION_BOOT_MINUTES`) ne peut même pas recevoir les rappels de `liveness`. Le flux se lit sur `gc events` (pas de bead de coordination requis) ; `lib/factory_session_boot.py` porte les règles, y compris le suivi d'une même identité à travers plusieurs id de bead de session (l'incident réel a alterné `creating`/`failed-create` sur des dizaines de beads). Le signalement nomme la session, son fournisseur/commande et le dernier `state_reason`/`close_reason`, et est envoyé directement à `${GC_ESCALATION_RECIPIENT:-human}` — jamais au Mayor, qui peut être précisément la session bloquée |

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
**nouveau** réveil envoyé au Mayor). `bin/campaign-pointer start`/`finish` —
la voie directe du Mayor pour poser `gc.current`/`gc.last_delivered` en
dehors de la boucle de la sentinelle — horodate aussi ce champ, pour que
cette livraison prouvée reste une preuve de vivacité même quand la boucle ne
l'a pas vue passer (af-20xom). Le garde-fou alerte si :

- la boucle est muette depuis **10 min** ;
- la campagne vit mais n'avance plus depuis **60 min** (réglable :
  `FACTORY_LIVENESS_MINUTES`).

L'horloge de progrès est composite. Au-delà de `gc.campaign_progress_at`, le
garde prend le plus récent des horodatages vérifiables du résultat courant et
des workflows que ce résultat nomme par les deux pointeurs de phase supportés,
`gc.backend_workflow` et `gc.frontend_workflow`, y compris leurs workflows
imbriqués et étapes actives, même dans un autre rig. Aucun autre champ ressemblant
à un pointeur n'est suivi. Quand les deux champs coexistent, un workflow
`in_progress` gagne sur un workflow `open`, et tout workflow actif gagne sur un
workflow fermé. Le `last_active` d'une session ne compte que si un bead de ce
sous-graphe enregistre explicitement son `gc.session_id` ou `gc.session_name` ;
voir une session exister ou être `active` sans heartbeat récent ne prouve rien.
Un workflow fermé ne prolonge jamais l'horloge ; avec `gc.outcome` non-pass, il
devient au contraire un signal de reprise : `factory-guard` ouvre un seul défaut
de vivacité, puis `factory-watchdog` le relance selon son cooldown existant.

Une pause volontaire (fenêtre de maintenance, quotas épuisés) est affichée,
jamais signalée comme panne. Les règles sont dans `lib/factory_liveness.py`.

---

## `./bin/factory-watchdog` — la surveillance qui page, pas seulement qui observe

La vivacité de `factory-guard` répond à « la campagne avance-t-elle ». Plusieurs
autres signaux peuvent rester muets même quand elle avance
(`INCIDENT_2026-09-16-silent-campaign-stall.md`, af-539b0) :

```bash
./bin/factory-watchdog                # par défaut : vérifie ET page (mail + bead)
./bin/factory-watchdog --check-only   # ne touche à rien, sort non-zéro si problème
```

| Contrôle | Ce qu'il fait |
|---|---|
| `gates` | une « Gate: human » ouverte depuis plus de 30 min (réglable) est re-signalée au Mayor, pas seulement laissée dans la file |
| `prs` | une PR du dépôt Factory en `CONFLICTING`, ou dont aucun contrôle CI n'a jamais démarré, après 30 min — distincte d'une PR qui attend simplement son tour |
| `workflows` | un bead molécule/workflow fermé `CLOSED` avec `gc.outcome` ≠ `pass` (le cas `on_fail=abort_scope` : chaque étape en aval passe `outcome=skipped` en silence) |
| `gh-auth` | `gh auth status` échoue (token WSL périmé/invalide) — dix scripts en dépendent (`reversibility-check`, `factory-guard`, `pr-autopilot`, `factory-do-work-workspace`, `factory-gh-rollup`, `factory-delivery-guard`, `deliver-close`, `factory-queue-guard`, `factory-watchdog`, `factory-main-gate`) et échouaient chacun silencieusement de son côté (af-539b0, 2026-09-18) ; **un seul** bead partagé nommant les dix scripts, **un seul** mail au Mayor par cooldown, et auto-résolu dès que `gh auth` revient — jamais un bead par script, jamais un par passage |
| `stall-frequency` | compte glissant sur 24h des transitions `BLOCKED_STALLED` dans `.gc/runtime/factory-continuity-history.json` (`lib/factory_continuity.py`) ; à partir de 5, **un seul** bead + mail au Mayor par cooldown, nommant l'état qui précédait chaque arrêt (« cause inconnue » si l'arrêt est le tout premier événement de l'historique) — un arrêt isolé se diagnostique déjà ; ce contrôle détecte le motif récurrent (audit d'observabilité, constat C3, 2026-09-18) |
| `sentinel-ticks` | rapproche les événements Gas City `order.fired` et `order.completed`/`order.failed` de `mayor-campaign` ; trois passages consécutifs d'au moins **45 s** signalent que la sentinelle touche sa limite dure de 50 s. Un seul bead + mail est créé, les relances respectent le cooldown, et un passage rapide ferme automatiquement le signalement (af-v0w20, 2026-09-21) |
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
jamais se lire comme un arrêt de toute la campagne. Le compte glissant
`stall-frequency` est en plus recalculé directement par `lib/factory_cockpit.py`
(même fonction pure `stall_frequency`, `lib/factory_watchdog.py`) et exposé
sous `today.stall_frequency` — visible dans le panneau même sous le seuil de
page, pas seulement une fois l'alerte déclenchée.

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
./bin/mayor-campaign repair --mayor  # restaure candidat/condition manquants (ADR-0023)
./bin/mayor-campaign scope <sha256:digest> --mayor  # voie exclusive d'un graphe approuvé
./bin/mayor-campaign scope clear --mayor            # lève explicitement ce scope
```

**À lire en premier dans toute nouvelle session.** Un `ERROR` sur `status`
signifie que la boucle de réveil est **morte**, pas qu'elle se repose — la
distinction est exactement ce qui a coûté une nuit le 2026-09-15.

`repair --mayor` est la porte qui restaure `gc.campaign_candidate`/`condition`
depuis la dernière paire valide (`_last`, tenue par `activate`/`resume`) et
normalise les pointeurs de coordination vides en `none`, sans jamais deviner
un candidat ; à défaut de dernière valeur valide, elle bloque la campagne
(`kind admin`) au lieu de deviner. `factory-guard` l'appelle à chaque passage
(af-hihkg).

Les transitions exigent le garde `--mayor`. C'est un garde « transition
délibérée », **pas** une revendication d'identité : déclarez l'auteur réel dans
`--cause`. Le Mayor lit ce champ et peut prendre une recommandation du PO pour
une décision de Benjamin.

Le scope `exclusive_graph` (ADR-0025) est plus fort qu'une priorité. Tant qu'il
est actif, la sentinelle ne peut choisir que les beads portant le digest exact
et `gc.plane=delivery`; elle ne retombe ni sur le produit, ni sur un ancien bead
Factory, ni sur l'échelle générative. Une frontière vide ou bloquée rend
`scoped_graph_waiting` à zéro appel modèle. Utiliser
`./bin/ticket-graph-publish validate|publish <draft>` pour la publication
atomique du draft approuvé, puis lever le scope seulement à la transition
explicitement autorisée.

### Oracle public d'une City fixture

`./bin/fixture-city-oracle run <scenario> --operator <adapter>
--publication-door <adapter>` exerce un intent synthétique uniquement par les
surfaces publiques de l'opérateur et de la porte de publication. Il recalcule
les digests, vérifie les Work Planes positifs, le convoy, les arêtes, les
révisions Git réellement assemblées, leur compatibilité publique et la
distinction Delivered/Accepted. Les adapters sont confinés par Bubblewrap sans
réseau ni accès au domicile hôte. Une injection `after-stage` doit laisser zéro
graphe, bead delivery ou convoy. Le résultat JSON est déterministe et ne dépend
pas du Cockpit V1. Contrat complet : `FIXTURE_CITY_ORACLE.md`.

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

Un bead déjà pris à l'échelon 2 n'attend pas aveuglément le délai de sécurité :
à chaque passage, la sentinelle relie le bead (ou ses références `gc.child_*`)
à son dernier workflow graph.v2. Dès que la racine et toutes ses étapes sont
fermées, elle réveille le Mayor pour finaliser, une seule fois. Le message dit
explicitement si un `gc.outcome` n'est pas `pass`; tant qu'une étape reste
ouverte, aucun réveil de finalisation n'est envoyé. Le délai de six heures reste
le filet de sécurité d'un travail réellement bloqué ou sans workflow canonique.
Cette vérification ramène donc l'attente de finalisation de 0–6 h au prochain
passage de sentinelle (contrat : moins de 5 min), sans appel de modèle.

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

L'acquittement durable du **premier** réveil (`wake_state=sent`, heure d'envoi,
compteur à zéro) est écrit avant l'appel mail. Si la commande mail rend une
erreur, la sentinelle remet la clé et l'état à zéro ; si le contrôleur la tue
brutalement pendant l'appel, le passage suivant respecte l'acquittement et ne
renvoie pas le même premier réveil. Le rappel à 30 min reste le filet de
sécurité si la mort est arrivée juste avant la livraison. C'est le choix
at-most-once qui corrige af-v0w20 : entre 00:10Z et 00:36Z le 2026-09-21, le
mail partait puis chaque passage mourait à 50 s avant l'ancien acquittement
post-envoi, produisant 14 copies en 24 min. `factory-watchdog` signale désormais
ce motif dès trois passages consécutifs d'au moins 45 s et auto-résout le
signalement au premier passage rapide.

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
compte, donc une limite Claude les épuise tous. Codex standard est son propre
pool.

Si **aucun** fournisseur ne reste pour les ouvriers, la campagne est mise en
pause (`limit`, cause `[provider-failover]`) avec l'heure de reprise la plus
proche, puis **reprise automatiquement**. Cela ne demande jamais Benjamin.

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
fusions anciennes, tandis qu'une livraison récente ou bloquante relance la
campagne immédiatement, sans attendre le garde de vivacité.

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
