# Un script de l'usine peut-il fusionner par lots sur ce dépôt ?

## Résumé

1. **Faisable sous conditions**, sans service payant, sans accès tiers, sans acteur de contournement et sans droit nouveau pour le jeton de l'usine.
2. Forme recommandée, la « PR de lot » : le script construit une branche « main + N PR », ouvre UNE PR vers main, la batterie tourne une fois dessus, et GitHub la fusionne par la porte actuelle (contrôle `Tests` requis, PR à jour avec main).
3. Les N PR passent alors à « merged » toutes seules : GitHub marque fusionnée une PR dont les commits de tête deviennent atteignables depuis la branche de base (doc GitHub, « Indirect merges »).
4. Condition 1 : le lot entre par un commit de fusion, pas par un squash. Aujourd'hui main est 100 % squash (200 derniers commits) : l'historique change de forme.
5. Condition 2 : les PR ordinaires ne lancent plus la batterie entière, sinon le lot ne fait rien gagner ; `.github/workflows/ci.yml` et `bin/pr-autopilot` changent.
6. Condition 3 : la preuve de l'ADR-0026 (« CI verte sur la tête exacte de la PR ») devient « batterie verte sur le lot qui contient cette tête » ; `bin/deliver-close` et `lib/factory_delivery_proof.py` changent ensemble.
7. Formes écartées ou secondes : push fast-forward façon bors-ng (demande de retirer la règle « PR obligatoire » ou un acteur de contournement) ; fusions une par une après un lot vert façon Prow Tide (main peut recevoir un état non testé).
8. **Fait nouveau, lu en direct** : le ruleset n'exige plus « PR à jour avec main » depuis le 2026-10-10 à 00:37 (Paris). La recherche de départ et les docs disent l'inverse.
9. Quatre comportements de GitHub restent à essayer sur un dépôt jetable avant la Spec (section « Non vérifié »).

Recherche du 2026-10-10, lectures en direct entre 01:05 et 01:15 (Paris), ticket af-8km43c.4 de la carte af-8km43c, sous-agent de la session opérateur po-agent/f944daf6. Branche jamais fusionnée `research/af-8km43c-lots-par-script`. Rien n'a été changé ni essayé : ni ruleset, ni CI, ni runner, ni push, ni PR.

Question (session parente) : un script de l'usine peut-il fusionner les PR par lots sur ce dépôt, et à quelles conditions ? Contrainte de Benjamin (carte, Q7) : script de l'usine, ni service payant ni accès tiers au dépôt.

## Vocabulaire

| Mot | Sens ici |
|---|---|
| Lot | N PR réunies sur une branche temporaire « main + N PR », testées par un seul run |
| Batterie | tous les tests de `bin/ci-run-tests` |
| Ruleset | jeu de règles GitHub posé sur une branche (ici `AF-main-protection` sur `main`) |
| Contrôle requis | résultat de CI que le ruleset exige avant toute entrée dans main (ici le job `Tests`) |
| « À jour avec main » | réglage `strict_required_status_checks_policy` : la PR doit contenir le dernier commit de main pour fusionner |
| Acteur de contournement | compte, rôle, équipe, application ou clé que le ruleset laisse passer outre ses règles (`bypass_actors`) |
| Fusion indirecte | PR marquée « merged » par GitHub parce que ses commits sont arrivés dans la branche de base par un autre chemin |
| Squash | fusion qui remplace les commits d'une PR par un seul commit neuf sur main |
| Fast-forward | main avance jusqu'à un commit qui la contient déjà : aucun commit n'est créé |
| Bissection | couper un lot rouge en deux et retester chaque moitié jusqu'à isoler la PR fautive |

## 1. L'état réel (lu le 2026-10-10 à 01:06)

Source : `gh api repos/saymyname-app/agent-factory/rulesets/23626687`, `.../rulesets/23626687/history`, `gh api repos/saymyname-app/agent-factory`, `gh auth status`, `gh api orgs/saymyname-app`.

| Élément | Valeur lue | Ce que cela permet ou interdit |
|---|---|---|
| Cible | `refs/heads/main`, actif | |
| `deletion` | présent | main ne peut pas être supprimée |
| `non_fast_forward` | présent | pas de push forcé |
| `pull_request` | 0 approbation ; méthodes `merge`, `squash`, `rebase` | toute entrée dans main passe par une PR ; les trois méthodes sont permises (pas de règle d'historique linéaire) |
| `required_status_checks` | `Tests`, `integration_id` 15368 (GitHub Actions) | le contrôle doit venir d'Actions : un statut posé à la main par le jeton ne compte pas |
| `strict_required_status_checks_policy` | **`false`** | une PR en retard sur main peut fusionner |
| `bypass_actors` | `[]` ; `current_user_can_bypass: never` | personne ne passe outre, pas même le compte administrateur de l'usine |
| Dépôt | privé ; `allow_auto_merge: true` ; `allow_update_branch: false` ; `delete_branch_on_merge: true` ; les trois méthodes ouvertes | |
| Plan | organisation `team` | rulesets disponibles ; file de fusion native non (recherche de départ) |
| Jeton de l'usine | compte `benjamin-hurand`, administrateur du dépôt ; portées `repo`, `workflow`, `read:org` | peut créer une branche, ouvrir et fusionner une PR, modifier le ruleset |
| Jeton des jobs de CI | lecture seule (`default_workflow_permissions: read`) | un job ne peut ni pousser ni fusionner |
| Runner | un seul, `factory-ci`, un job à la fois ; variable `FACTORY_CI_RUNNER=self-hosted` | |
| Forme de main | les 200 derniers commits de la ligne principale ont un seul parent (squash) ; 15 dernières PR fusionnées par `benjamin-hurand` | |

### Fait nouveau : « à jour avec main » est désactivé depuis 00:37

| Version du ruleset | Date (Paris) | `strict` |
|---|---|---|
| 51244750 | 2026-09-29 08:08 | `true` |
| 52640560 (actuelle) | **2026-10-10 00:37** | **`false`** |

- Auteur des deux versions : le compte 80873224 (`benjamin-hurand`), qui est aussi celui du jeton de l'usine : l'historique ne dit pas si c'est lui ou une session d'agent.
- `allow_update_branch` est aussi à `false` : c'est exactement l'effet de `bin/enable-strict-main-protection --rollback`.
- Contredit : la recherche de départ (« `strict_required_status_checks_policy: true` »), `docs/DELIVERY.md` (« Merge safety — `main` requires up-to-date branches »), le commentaire de `.github/workflows/ci.yml` (« No run on `push` to main: the ruleset requires a pull request whose branch is up to date with main »), et la note de la carte (« ne veut PAS dire qu'un réglage du ruleset change pendant la carte »).
- Effet : deux PR vertes chacune sur un ancien main peuvent se combiner en un main rouge sans conflit de texte, et aucun run ne tourne sur main (pas d'événement `push` dans la CI). C'est la forme C ci-dessous, sans le lot.
- Aucun bead trouvé par `bd search` sur `strict_required_status_checks_policy` ni sur `enable-strict-main-protection`. Cause non établie.
- À 01:09, une PR ouverte (#490), dans l'état `BLOCKED` (contrôle en cours) ; main à `6122051`.

## 2. Ce que GitHub documente (sources primaires)

| Sujet | Ce que dit la doc | Source |
|---|---|---|
| PR marquée fusionnée par un autre chemin | « A pull request can be marked as merged if its head branch commits become reachable from the base branch » ; cela arrive quand les mêmes commits sont fusionnés par une autre PR ou poussés directement ; la PR est marquée `merged` même si ses propres règles de protection n'étaient pas satisfaites | [About pull request merges, « Indirect merges »](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/about-pull-request-merges) |
| Squash | les commits de la PR deviennent un seul commit sur la base ; les commits d'origine n'y sont pas | même page |
| Rebase | « creates new commit SHAs » | même page |
| Contrôle requis, mode strict | « The topic branch must be up to date with the base branch before merging » | [Available rules for rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets) |
| Sur quel commit le contrôle doit être vert | sur le dernier commit ; si le commit de fusion d'essai porte un statut c'est lui, sinon la tête | [Troubleshooting required status checks](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks) |
| Pousser soi-même une PR prête | « Pull requests that are up-to-date and pass required status checks can be merged locally and pushed to the protected branch », sans relancer les contrôles sur le commit de fusion | même page |
| Job sauté par une condition (`if:`) | il rapporte « Success » : il satisfait le contrôle requis | même page |
| Workflow sauté par un filtre de branche ou de chemin | le contrôle reste « Pending » et bloque la fusion | même page |
| Contrôle venu d'une autre source que celle exigée | la fusion est refusée | même page |
| Règle « PR obligatoire » | « all changes to the target branch be associated with a pull request » | Available rules for rulesets |
| Historique linéaire | règle distincte, qui interdit les commits de fusion ; absente ici | même page |
| Acteurs de contournement possibles | rôles du dépôt (admin, maintain, write), propriétaires de l'organisation, équipes, applications GitHub, Dependabot ; par l'API aussi `DeployKey` et `User` | [Creating rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository), [REST rules](https://docs.github.com/en/rest/repos/rules) |
| Modes de contournement | `always` ; `pull_request` (contourne seulement par une PR, ne peut pas pousser en direct) ; `exempt` (les règles ne tournent pas, aucune trace d'audit) | REST rules |
| Portée d'un contournement | il vaut pour tout le ruleset, pas pour une règle | About rulesets (le contournement est une propriété du ruleset) |
| Fusion d'une PR par l'API | `PUT /repos/{owner}/{repo}/pulls/{n}/merge`, `merge_method` = `merge`, `squash` ou `rebase`, `sha` = tête attendue (409 sinon) | [REST pulls](https://docs.github.com/en/rest/pulls/pulls) |
| `merge_commit_sha` après fusion | commit de fusion, commit de squash, ou commit où la base est arrivée (rebase) | même page |
| Rulesets et plan | disponibles sur Team pour un dépôt privé | [About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets) |

Conséquence directe : pour que les N PR d'un lot soient marquées « merged » sans que le script y touche, leurs commits de tête doivent arriver tels quels dans main. Donc un lot construit par de vrais `git merge` de chaque tête, et entré dans main par un commit de fusion ou par fast-forward. Un squash ou un rebase du lot crée des commits neufs : les PR resteraient ouvertes.

## 3. Comment font bors-ng, Prow Tide et Rust

| Outil | Formation du lot | Entrée dans main | PR fautive | PR marquées fusionnées | Réglage de protection |
|---|---|---|---|---|---|
| bors-ng ([README](https://github.com/bors-ng/bors-ng), [référence](https://bors.tech/documentation/)) | un commit de fusion « main + toutes les PR du lot », poussé sur la branche `staging` | « the main branch gets fast-forwarded to meet the staging branch » : push direct par l'application bors | bissection : le lot est coupé en deux lots remis en file ; un lot d'une seule PR est renvoyé à son auteur | par fusion indirecte (les têtes sont dans main) ; avec `use_squash_merge`, bors ferme lui-même la PR et préfixe son titre « [Merged by Bors] » | le statut exigé est lu sur le commit de `staging` (`status` dans `bors.toml`) ; bors doit pouvoir pousser sur main |
| Prow Tide ([doc](https://docs.prow.k8s.io/docs/components/core/tide/), [mainteneurs](https://docs.prow.k8s.io/docs/components/core/tide/maintainers/), [code](https://github.com/kubernetes-sigs/prow/blob/main/pkg/tide/github.go)) | un job « batch » teste la base + plusieurs PR | chaque PR du lot est fusionnée l'une après l'autre par l'API de fusion (`mergePRs` : boucle, `SHA: pr.HeadRefOID`, 5 s entre deux) | pas de bissection : si le lot échoue, Tide se rabat sur une PR seule déjà verte | par la fusion normale de chacune | la doc déconseille « à jour avec main » : inutile et gênant avec Tide |
| Rollups de Rust ([forge](https://forge.rust-lang.org/release/rollups.html)) | une personne crée UNE PR « rollup » qui réunit des PR peu risquées | la PR rollup est approuvée et fusionnée comme une autre | à la main : lire les journaux, retirer la PR suspecte (`r-`), refaire le rollup | non décrit par la page (voir « Non vérifié ») | les PR à risque sont exclues (`rollup=never`) |

- bors-ng est déprécié et renvoie à la file de fusion native de GitHub (non disponible ici).
- La file native elle-même construit des branches temporaires, exige l'événement `merge_group` et « provides the same benefits as the Require branches to be up to date before merging » ([doc](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)).
- Les trois formes ci-dessous sont ces trois modèles, dans l'ordre : Rust (PR de lot), bors-ng (fast-forward), Tide (fusions successives).

## 4. Les formes possibles, classées

### Forme A (recommandée) : la PR de lot, fusionnée par la porte actuelle

Mécanisme :
1. Le script choisit N PR ouvertes prêtes, crée une branche `lot/<id>` sur le dernier main, y fait un `git merge --no-ff` de chaque tête de PR, dans l'ordre.
2. Il ouvre une PR `lot/<id>` → `main`. L'événement `pull_request` lance la batterie comme aujourd'hui ; le job `Tests` s'attache à cette PR.
3. Vert : il fusionne par l'API avec `merge_method=merge` et `sha` = la tête testée. Rouge : il ferme la PR de lot et coupe le lot.
4. GitHub marque les N PR « merged » (fusion indirecte).

| Question | Réponse |
|---|---|
| Qui pousse « main + lot » dans main ? | personne : GitHub fusionne la PR de lot, comme toute PR |
| Quelle règle remplace « à jour avec main » ? | aucune : elle est **gardée** (remise à `true`) et porte sur la PR de lot. Si main a bougé depuis la construction du lot, GitHub refuse la fusion |
| Ce qui garantit qu'un commit de main est couvert | le ruleset, pas le script. PR de lot à jour + fusion par commit de fusion : l'arbre posé sur main est celui de la tête du lot, et c'est aussi l'arbre du commit de fusion d'essai que la batterie a testé. Une PR ordinaire fusionnée hors lot resterait soumise au même contrôle |
| Acteur de contournement | aucun |
| Changement du ruleset | aucun par rapport au 2026-09-29 (il faut seulement que `strict` revienne à `true`) |
| Jeton | celui que l'usine détient déjà (`repo`) ; `workflow` sert pour modifier `ci.yml` |
| Atomicité | les N PR entrent ensemble ou pas du tout |
| Forme de main | un commit de fusion par lot sur la ligne principale ; derrière lui, les commits bruts des PR (aujourd'hui : un commit de squash par PR) |

Limite : seuls les commits de la ligne principale de main (un par lot) correspondent à un arbre testé. Les commits intermédiaires des PR entrent dans l'historique sans avoir été testés un par un ; aujourd'hui le squash les fait disparaître.

### Forme B : fast-forward de main jusqu'au lot (modèle bors-ng)

Mécanisme : le script pousse la branche de lot, un run la teste, puis il pousse main en fast-forward jusqu'à la tête du lot.

| Question | Réponse |
|---|---|
| Qui pousse ? | le script, avec le jeton de l'usine ou une clé dédiée |
| Ce que le ruleset actuel en dit | refusé : la règle `pull_request` exige une PR, et il n'y a aucun acteur de contournement |
| Deux façons de l'ouvrir | (1) retirer la règle `pull_request` et garder le contrôle requis : selon la doc des branches protégées, des commits peuvent être poussés directement une fois les contrôles requis verts ; (2) donner un contournement au pousseur |
| Risque du contournement | il vaut pour tout le ruleset : un rôle admin en mode `always` laisse toute session d'agent qui a le jeton pousser n'importe quoi dans main, contrôle requis compris. Une clé de déploiement dédiée limite le pousseur mais reste un secret nouveau |
| Ce qui garantit la couverture | (1) GitHub, si le contrôle requis est bien évalué sur le commit poussé ; (2) le script seul |
| Avantage sur A | le commit qui arrive sur main est exactement celui qui a été testé (pas un commit de fusion de même arbre) ; pas de PR de lot à ouvrir |
| Coût | la porte de main change (décision de Benjamin) ; un nouveau déclencheur de CI sur la branche de lot ; `bin/factory-main-gate` relancerait la batterie entière sur l'hôte à chaque push vers main |

### Forme C : fusions une par une après un lot vert (modèle Tide)

Mécanisme : le lot est testé sur une branche temporaire ; vert, le script fusionne chaque PR par le chemin actuel (`gh pr merge --squash`), sans la règle « à jour ».

| Question | Réponse |
|---|---|
| Changement du ruleset | `strict` à `false` (c'est l'état lu ce soir) ; et le contrôle `Tests` devrait être vert sur chaque tête de PR, qui n'a pas eu de batterie à elle |
| Comment rendre `Tests` vert sur chaque PR | soit chaque PR lance sa batterie (aucun gain), soit le script pose lui-même le statut, ce qui exige de retirer `integration_id` (toute session ayant le jeton pourrait alors poser un vert) |
| Ce qui garantit la couverture | rien côté GitHub. Si la 3e fusion sur 5 échoue, ou si une autre PR fusionne entre-temps, main porte un état que personne n'a testé |
| Avantage | garde un squash par PR, un vrai « merged » et un `mergeCommit` par PR : c'est ce que lisent les outils actuels |

### Classement

| Rang | Forme | Garantie de couverture | Porte de main | Ce qui change |
|---|---|---|---|---|
| 1 | A, PR de lot | tenue par GitHub | inchangée (strict remis) | forme de l'historique, CI des PR ordinaires, preuve ADR-0026 |
| 2 | B, fast-forward | tenue par GitHub si la règle PR est retirée, par le script seul avec un contournement | changée | porte, déclencheur de CI, garde locale de push |
| 3 | C, fusions successives | non tenue | affaiblie | peu d'outils, mais la qualité visée (b) de la carte n'est plus assurée |

## 5. Ce que les outils lisent aujourd'hui et ce qui casserait

Lu sur `origin/main` à `6122051`.

| Outil | Ce qu'il lit ou fait | Avec la forme A |
|---|---|---|
| `bin/pr-autopilot`, armement | arme l'auto-fusion de toute PR ouverte, verte, non en retard (`gh pr merge --auto --squash --delete-branch`) ; chemin direct en squash si GitHub tarde (af-n8gft2) | **casse le principe** : il fusionnerait les PR une par une avant le lot. Il ne doit plus armer que la PR de lot, en méthode `merge` |
| `bin/pr-autopilot`, PR en retard | met à jour la plus ancienne PR `BEHIND`, une par passe (`update-branch`) | à retirer pour les PR ordinaires (chaque mise à jour relance un run) ; à garder pour la PR de lot, ou la reconstruire |
| `bin/pr-autopilot`, PR sans contrôle | une PR dont `Tests` n'a jamais rapporté est étiquetée bloquée et signalée | casse si les PR ordinaires ne lancent plus `Tests` : fausse alerte sur chacune |
| `bin/pr-autopilot`, contrôle rouge | relance une fois, puis rend le ticket ou ouvre un bead P1, par PR | à déplacer : le rouge est celui du lot, la PR fautive sort de la bissection |
| `bin/pr-autopilot`, rapprochement | `gh pr list --state merged --base main` puis lien par nom de branche (`gc.work_branch`) | tient, si la fusion indirecte donne bien l'état `MERGED` |
| `bin/deliver-close` | exige : PR `MERGED`, `mergedAt`, `mergeCommit.oid` de 40 caractères, et un run `pull_request` du workflow `Factory CI`, réussi, dont `head_sha` égale la tête de la PR | **refuse** : la tête d'une PR ordinaire n'a plus de run de batterie. Aucun ticket ne se fermerait |
| `lib/factory_delivery_proof.py` | `gc.ci_head_sha` doit égaler `gc.pr_head` ; `merged_sha` doit égaler `gc.merge_commit` | à faire évoluer avec `deliver-close` : nouvelle preuve « run vert sur la tête du lot ; la tête de la PR est un ancêtre de la tête du lot ; le lot est dans main ». Lu aussi par `factory-waiting-guard`, `factory-delivery-guard`, `factory-guard` |
| ADR-0026 | point 3 : run réussi sur la tête exacte | amendement nécessaire (autorité : Benjamin) |
| `.github/workflows/ci.yml`, événements | `pull_request` vers main, et `workflow_dispatch` | la PR de lot déclenche la batterie sans changement. Mais chaque PR ordinaire la déclenche aussi : à restreindre |
| `.github/workflows/ci.yml`, piège | | ne pas sauter le job `Tests` par un `if:` sur les PR ordinaires : un job sauté rapporte « Success » et rendrait la PR fusionnable sans batterie. Il faut que `Tests` ne soit jamais rapporté sur elles (workflow ou nom de job distinct) |
| `.github/workflows/ci.yml`, sélection | `--changed-since HEAD^1` sur le commit de fusion d'essai | tient : pour la PR de lot, `HEAD^1` est main, donc le changement lu est le lot entier |
| `.github/workflows/ci.yml`, concurrence | un groupe par numéro de PR, `cancel-in-progress` | tient ; un lot reconstruit annule son run précédent |
| `bin/factory-main-gate` (crochet `pre-push`) | lance la batterie sur l'hôte avant tout `git push` vers `refs/heads/main` | non touché (A fusionne par l'API). Avec B, il relancerait 20 min de batterie à chaque lot |
| Racine vivante (`bin/factory-guard`, `live-root-sync`) | `git merge --ff-only origin/main` si l'arbre suivi est propre | tient quelle que soit la forme des commits de main |
| `bin/outcome-promote` | crée un commit de fusion et le pousse en direct sur la branche protégée, avec bail (`--force-with-lease=refs/heads/<branche>:<pointe lue>`) ; refuse toute session d'agent | voir le précédent ci-dessous |

L'ADR-0020 (garde de push vers main) n'est plus dans `docs/decisions/` : il est dans `legacy/docs/decisions/ADR-0020-main-landing-gate.md`. `docs/DELIVERY.md` y renvoie encore.

### Le précédent `bin/outcome-promote`

- C'est un précédent de **conception**, pas de fonctionnement sur ce dépôt : un push direct, protégé par un bail sur la pointe lue, fait par un ordre de l'usine et jamais par une session d'agent.
- `docs/OUTCOME_PROMOTE.md` l'écrit lui-même dans ses limites : « A branch protection that refuses it leaves the Outcome accepted and unmerged ».
- Sur `agent-factory`, le ruleset actuel refuserait ce push (règle `pull_request`, contrôle requis absent du commit de fusion neuf, aucun contournement). Déduit du ruleset, non essayé.
- Il ne donne donc aucun droit déjà acquis à la forme B. Il donne deux idées réutilisables : le bail (ne bouger main que depuis la pointe lue) et le refus des sessions d'agent.

## 6. Limites

| Limite | Ce qui se passe | Ce que font les autres |
|---|---|---|
| PR en conflit de texte avec main ou avec une PR déjà dans le lot | le `git merge` échoue à la construction : la PR est laissée hors du lot (lot suivant, ou rendue à son auteur par le chemin `DIRTY` de `pr-autopilot`) | bors-ng : la PR en conflit attend derrière |
| PR incompatibles sans conflit de texte | le lot est rouge ; la bissection isole l'une des deux | bors-ng coupe en deux ; Tide retombe sur une PR seule ; Rust retire à la main |
| Coût d'un lot rouge sur un seul runner | chaque moitié retestée coûte une batterie (16 à 55 min mesurées dans la recherche de départ) | Rust exclut d'avance les PR à risque |
| Squash | aujourd'hui toute PR entre par squash. Un lot en squash ne marque pas les PR « merged » : le script devrait les fermer lui-même (comme bors-ng avec `use_squash_merge`), et `deliver-close` ne lirait plus `MERGED` | |
| Commits de fusion | permis par le ruleset (pas de règle d'historique linéaire) ; main en compte déjà 29 anciens sur 571 commits | |
| Suppression des branches | `--delete-branch` n'est plus passé par PR ; le réglage du dépôt `delete_branch_on_merge` est à `true`, son effet sur une fusion indirecte n'est pas établi | bors-ng a une option dédiée (`delete_merged_branches`) |
| Un job à la fois | le run du lot et les runs courts des PR ordinaires se partagent le runner (tickets af-8km43c.6 et .7) | |
| Droits | forme A : aucun droit nouveau. Forme B : modifier le ruleset, et selon le choix une clé ou une application nouvelle. Forme C : modifier le ruleset | |

## 7. Conclusion

**Faisable sous conditions.** Formes classées : A (PR de lot fusionnée normalement), B (fast-forward), C (fusions successives). Seule A garde la porte de main telle qu'elle était le 2026-09-29 et laisse GitHub, et non le script, garantir que chaque commit de la ligne principale de main a été couvert par une batterie verte.

Conditions de A : `strict` remis à `true` ; lot construit par de vrais commits de fusion et entré par un commit de fusion ; les PR ordinaires ne rapportent plus `Tests` ; `pr-autopilot` n'arme plus que la PR de lot ; `deliver-close`, `factory_delivery_proof.py` et l'ADR-0026 acceptent la preuve par le lot ; les quatre comportements de la section « Non vérifié » essayés d'abord.

### Questions que seul Benjamin peut trancher

1. **Le ruleset de ce soir.** `strict` est à `false` depuis 00:37 : est-ce voulu ? Sinon, le remettre (`bin/enable-strict-main-protection`). Tant qu'il reste ainsi, main peut recevoir une combinaison jamais testée.
2. **La forme de l'historique de main.** Accepter un commit de fusion par lot avec les commits bruts des PR derrière (forme A), ou tenir à un commit de squash par PR (ce qui mène à C, ou à des PR fermées par le script et non « merged »).
3. **La preuve de livraison.** Remplacer « CI verte sur la tête exacte de la PR » (ADR-0026) par « batterie verte sur le lot qui contient cette tête ».
4. **Un essai sur un dépôt privé jetable** de l'organisation, pour lever les points non vérifiés. Créer un dépôt est de son ressort.
5. **Ce qu'une PR ordinaire lance avant d'entrer dans un lot** : rien, les contrôles de règles, ou un étage court (lié au ticket af-8km43c.5 et à la sélection de tests).
6. Seulement si A est écartée : retirer la règle « PR obligatoire » ou créer un acteur de contournement (forme B), avec ce que cela ouvre.

## Non vérifié

- **Les champs d'une PR fusionnée indirectement** : la doc dit qu'elle est marquée `merged`, mais ne dit pas ce que valent `mergeCommit`/`merge_commit_sha`, `mergedAt` et `mergedBy`. `deliver-close` les lit. Aucun cas dans l'historique du dépôt : sur 478 PR fusionnées, aucune sans `mergeCommit`, aucune paire partageant le même ; les PR #41 à #48 hors ligne principale sont des fusions normales reprises plus tard.
- **La fusion indirecte quand la PR de lot entre par un commit de fusion fait par GitHub** : attendue (les têtes deviennent atteignables), non essayée ici.
- **La suppression automatique de la branche** d'une PR fusionnée indirectement.
- **Forme B** : qu'un ruleset sans règle `pull_request` accepte le push d'un commit dont `Tests` est vert, et qu'un run déclenché par `push` ou à la main sur la branche de lot satisfasse le contrôle requis. `docs/OPERATIONS.md` dit d'un run lancé à la main qu'il « is not the `pull_request` run the ruleset reads » ; non revérifié.
- Que `mergeStateStatus` ne rapporte plus `BEHIND` quand `strict` est à `false` (connaissance de l'agent, pas lue dans une doc) : si c'est le cas, `pr-autopilot` ne met plus aucune PR à jour depuis 00:37.
- Qui a changé le ruleset à 00:37, et pourquoi.
- Le texte entier de la section « Indirect merges » et de la note « merged locally and pushed » : l'outil de lecture n'a rendu que des extraits ; les phrases citées entre guillemets sont celles qu'il a rendues telles quelles.
- La façon dont les PR membres d'un rollup de Rust sont marquées : la page de la forge ne le dit pas.
- Tide : la fonction `tryMerge` (ce qui arrête la boucle quand la base a bougé) n'a pas été lue.
- Qu'un contournement ne puisse pas être limité à une règle : déduit de la forme de l'API (`bypass_actors` au niveau du ruleset), pas d'une phrase de la doc. Deux rulesets séparés le permettraient ; non essayé.
- Le refus par GitHub du push de `bin/outcome-promote` sur ce dépôt : déduit, non essayé.
- Aucun chiffre de durée n'a été remesuré ; ceux de la recherche de départ ne sont repris que pour l'ordre de grandeur.
