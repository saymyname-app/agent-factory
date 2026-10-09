## `./bin/method-check` — chaque exigence a-t-elle son mécanisme, chaque écart sa raison ?

**Deux contrôles en lecture seule sur ce que l'usine dit de sa propre
méthode** (D01 T31, Spec af-wf4w5r §9 et §16). Ils tournent à chaque run de
la CI de l'usine par `tests/method-check-test.py` : une pull request qui
casse l'un des deux est rouge.

```bash
./bin/method-check table      # docs/REQUIREMENT_TABLE.md
./bin/method-check register   # docs/ADAPTATION_REGISTER.md
```

- **`table`** : la table exigence → mécanisme → preuve. Rouge, en nommant la
  ligne, si un mécanisme est vide, ne nomme aucune commande (`bin/<nom>`),
  nomme une commande qui n'est pas un fichier exécutable de `bin/`, ou si la
  preuve est vide. Renommer une commande citée rend donc sa ligne rouge.
- **`register`** : l'Adaptation Register. Rouge si une entrée `AR-NNN` n'a
  pas de raison (champ `But`), si un écart de la liste « Écarts de la Spec
  D01 » ne nomme aucune entrée, nomme une entrée absente, ou une entrée dont
  le champ `Baseline` ne nomme pas la base de comparaison v1.3.1.
- **Sorties** : 0, une ligne ; 1, une raison en français par ligne sur
  stderr, chacune avec sa ligne ou son entrée ; 2, usage. `--root <dossier>`
  fait lire un autre arbre (les tests l'emploient sur une copie).
- **Limites** : le contrôle lit des noms et des champs, pas le fond. Il ne
  prouve ni qu'une commande tient l'exigence de sa ligne, ni qu'une raison
  est bonne, ni que la liste des écarts est celle de la Spec : la liste des
  lignes de la Spec §9 et des écarts de la Spec §16 est tenue par le test.

Détail : `docs/REQUIREMENT_TABLE.md`, `docs/ADAPTATION_REGISTER.md`.

---
