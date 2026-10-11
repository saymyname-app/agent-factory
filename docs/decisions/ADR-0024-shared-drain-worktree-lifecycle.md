# ADR-0024 : cycle de vie du worktree pour un drain partagé

- Statut : Accepté
- Date : 2026-09-21
- Autorité : bead `af-5z6p7`, autorisé par le run `smb-817d`
- Portée : fork Factory de `build-basic`, mode `drain_policy=same-session`

## Contexte

Le run guarded `smb-817d` a échoué avant toute lecture de source. Le drain
partagé avait bien matérialisé ses workflows `do-work-item`, mais aucun acteur
n'avait créé le worktree qu'ils exigent. Trois tentatives bornées ont donc
échoué avec `source anchor smb-rtut6 has no work_dir metadata`, puis les étapes
suivantes ont été sautées. Le contrôle fail-closed de `do-work-item` était
correct : utiliser `gc.work_dir` aurait envoyé l'ouvrier dans le checkout de
lancement et l'affaiblir n'était pas acceptable.

Le partage de session fourni par Gas City est un contrat d'ordonnancement :
`single_lane=true`, réservation exclusive et `skip_remaining` après échec. Il
ne constitue pas à lui seul un cycle de vie Git. Le drain séparé ne rencontrait
pas ce trou parce que sa formule enfant `do-work` possède une étape
`prepare-worktree` par item.

## Décision

La Factory ajoute un adaptateur local autour du drain partagé, sans forker le
contrôleur Gas City :

1. `prepare-shared-worktree`, entre la décomposition et le drain, crée ou
   reprend exactement un worktree et une branche déterministes pour la racine
   `build-basic`.
2. `bin/factory-shared-drain-workspace prepare` inscrit le même chemin absolu
   `work_dir` sur chaque source anchor du convoy, ainsi que la branche, la base,
   le propriétaire et l'ordre. Il vérifie immédiatement les lectures retour.
3. `do-work-item` garde son contrôle existant : aucun accès source si le chemin
   manque, pointe sur le launcher ou n'est pas le worktree autoritaire. Les
   items restent séquentiels et leurs commits s'accumulent sur la même branche.
4. La revue existante consomme les source anchors et ce worktree. La publication
   appelle l'adaptateur une fois pour pousser la branche et créer ou réutiliser
   une seule PR.
5. `cleanup-shared-worktree`, teardown de `build-pipeline`, retire le worktree
   propre et les pointeurs `work_dir` après succès comme après échec. Un état
   sale est conservé avec `gc.shared_worktree_cleanup=preserved_dirty` : aucune
   donnée de récupération n'est détruite.
6. Le chemin `drain_policy=separate` et sa formule enfant `do-work` ne changent
   pas.

La racine conserve `gc.work_dir` comme checkout de lancement. Le chemin
d'implémentation distinct est `gc.shared_worktree`; les source anchors seuls
portent `work_dir`. Cette séparation empêche une ambiguïté entre le lieu où
s'exécutent les contrôles de build et celui où les agents lisent/modifient le
code.

## Conséquences selon ADR-0017

1. **Vérifié** — `tests/factory-shared-drain-workspace-test.sh` utilise un
   dépôt bare, un launcher et deux items dépendants jetables. Il prouve un seul
   worktree partagé avant les commits, l'ascendance item 1 → item 2, la
   configuration `skip_remaining`, une seule PR idempotente, le retrait de
   l'enregistrement Git et la préservation d'un état sale. Le même test verrouille
   la forme inchangée du drain séparé. `tests/build-basic-fail-fast-test.py`
   couvre aussi le setup dans la portée et le teardown hors du body.
2. **Autonomie accrue** — plus aucune intervention humaine n'est nécessaire
   pour ajouter `work_dir` avant le premier item ou rassembler manuellement les
   commits de plusieurs items avant revue/publication.
3. **Optimisation** — un convoy de N items same-session utilise 1 worktree,
   1 branche et au plus 1 PR, au lieu d'un cycle par item ou d'un run bloqué et
   relancé. La préparation, la publication idempotente et le nettoyage sont L0
   (Bash/Git), sans appel modèle supplémentaire.
4. **Documentation agents et humain** — l'invariant est routé pour les agents
   par `docs/CONTEXT_INDEX.md` sans faire dépasser le budget de 8 KiB du
   bootstrap `AGENTS.md`; l'explication opérateur en français est dans
   `docs/DELIVERY.md`; cette ADR porte le contrat structurel.

## Risques et reprise

- Une publication échouée laisse le worktree et la branche en place ; aucune
  suppression automatique ne doit précéder la récupération.
- Le teardown refuse de supprimer un worktree sale. `factory-guard` peut alors
  le nommer, mais ne doit pas inventer ni forcer une livraison.
- La branche est poussée sans force. Un conflit non fast-forward reste un échec
  visible à résoudre, pas une autorisation implicite d'écraser le distant.
- Une branche locale propre peut survivre au teardown lorsque la publication
  est désactivée ; elle ne verrouille pas Git comme le ferait un worktree
  enregistré.

## Liens

- ADR-0017 — quatre conditions pour toute amélioration Factory.
- ADR-0022 — interdiction mécanique de modifier le live root.
- `formulas/build-basic.formula.toml` — raccord graph.v2.
- `bin/factory-shared-drain-workspace` — porte déterministe.
- `tests/factory-shared-drain-workspace-test.sh` — preuve de régression.
