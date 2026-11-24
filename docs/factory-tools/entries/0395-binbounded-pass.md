## `./bin/bounded-pass` — une passe d'ordre coupée par la charge est reportée

**Lance la passe d'un ordre dans son budget ; une passe coupée est reportée
(sortie 0), seules trois passes coupées de suite font échouer l'ordre**
(règle `S.load-cut` de `docs/DEFECT_CLASSES.md`, af-56yoam.7). Sous une forte
charge, chaque lecture d'une passe saine est plus lente, aucune n'est
bloquée ; la passe suivante relit le même état. **Gain** : quatre ordres
codaient chacun ce report (un `timeout`, un fichier de compte, une limite de
3) ; il est écrit une fois, et le cinquième ordre n'a plus à le recopier.

```bash
./bin/bounded-pass convoy-parent-sweep --budget 90 -- gc convoy check --json
./bin/bounded-pass factory-watchdog --budget 150 --deferred-exit 75 -- bin/factory-watchdog --quiet
```

- **Mécanisme** : la passe tourne dans une session à elle, dont le groupe
  meurt avec `bounded-pass` (`lib/bounded_process.py`). Au budget, le groupe
  reçoit SIGTERM, puis SIGKILL après `--kill-after` secondes (5) ; tout
  processus que la passe a laissé dans un autre groupe (un `timeout(1)`)
  porte `BOUNDED_PASS_ID` dans son environnement et est tué aussi. Une passe
  qui sort le code de `--deferred-exit` a renoncé d'elle-même dans son
  budget : elle compte comme coupée.
- **Le compte** : `.gc/runtime/<ordre>-deferred-passes` sous `FACTORY_ROOT`.
  Une passe coupée l'augmente et sort 0 avec `<ordre>: budget exceeded after
  <n>s — pass deferred (k of 3 in a row, loadavg …)` ; la troisième de suite
  sort 2 avec `3 passes in a row cut short`, et `on-order-failed` la voit.
  Une passe qui finit, quel que soit son code, efface le compte et rend son
  propre code.
- **N** est la constante `DEFER_LIMIT` de `bin/bounded-pass`, lue là seulement.
- **Ses ordres** : `convoy-parent-sweep`, `planning-artifacts-close`,
  `factory-watchdog` et `pr-autopilot` s'y lancent eux-mêmes, avec leur
  budget. **Sorties** : le code de la passe ; 0 une passe reportée ; 2 trois
  coupées de suite, ou un usage refusé.
