## `./bin/factory-maintain` — l'entretien ADMIN autorisé

Les cinq gestes de l'allowlist permanente passent uniquement par cette porte :
`restart-service`, `prune-merged-branches`, `clean-worktrees`, `rotate-logs` et
`reload-city-config`. Chaque action écrit sa preuve et son annulation dans
`var/factory-maintain.log` ; une opération hors de cette liste reste ADMIN.

`clean-worktrees` ne retire jamais un arbre sale. Git prouve normalement qu'un
HEAD est poussé et fusionné. Après une fusion squash suivie de la suppression de
la branche distante, cette preuve locale disparaît : la commande accepte alors
uniquement une PR GitHub fusionnée dont le nom de branche historique et le
`headRefOid` correspondent exactement à la branche et au HEAD locaux. Le numéro
de PR et `proof=github-pr-merged` entrent dans le journal. CLI absente, délai
dépassé, réponse illisible, OID différent ou PR non fusionnée : aucune
suppression ; le chemin existant de refus ou d'escalade reste en vigueur.

`prune-merged-branches` applique la même preuve aux branches locales, lue en
une seule requête paginée de toutes les PR fusionnées : une branche que Git
ne voit ni poussée ni fusionnée dans `main` est supprimée seulement si une PR
fusionnée de ce nom tient son HEAD, comme tête ou comme commit antérieur à
sa tête (af-tdpbg1 : sans elle, aucune branche fusionnée par squash n'était
élaguée et 858 branches s'étaient accumulées dans la racine vivante). Le
journal porte `pr=<n>` et une annulation qui récupère d'abord
`pull/<n>/head`. L'ordre `prune-merged-branches` la lance chaque jour à
05:20 (heure de l'hôte), après `clean-worktrees` de 05:00.

---
