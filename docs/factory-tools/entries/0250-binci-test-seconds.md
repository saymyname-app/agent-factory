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
