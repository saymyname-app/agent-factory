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
