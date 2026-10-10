## `./bin/ci-test-ceiling` — un fichier de test dépasse-t-il 120 secondes ?

**Le plafond de durée par fichier de test, tenu par du code** (Spec CI01,
af-q9urgr §3 ; la règle est `docs/TEST_GUIDELINE.md`, point 5). Il lit les
durées que la CI enregistre déjà (`config/ci-test-seconds.tsv`) et ne mesure
rien. Il tourne à chaque run de la CI de l'usine par
`tests/ci-test-ceiling-test.py` : une pull request qui enregistre un fichier
au-dessus du plafond est rouge.

```bash
./bin/ci-test-ceiling check   # lecture seule
./bin/ci-test-ceiling prune   # retire de la liste connue les fichiers repassés sous le plafond
```

- **Rouge**, en nommant le fichier : un fichier de test au-dessus de 120 s ;
  une exception écrite sans raison ; une ligne ajoutée à la liste connue ;
  une ligne de la liste dont le fichier n'est plus au-dessus de 120 s.
- **Exception écrite** : une ligne du fichier de test,
  `# ci: over-ceiling — <raison>`. Le modèle laissé tel quel ou une raison
  de moins de 10 caractères est refusé.
- **Durées illisibles** : fichier absent, sans aucune durée, ou portant une
  ligne qui n'est ni un commentaire ni `<chemin><TAB><secondes>` : rouge, en
  nommant la ligne. `prune` ne touche alors pas à la liste.
- **Liste connue** : `config/ci-test-ceiling-known.txt`, les 20 fichiers
  déjà au-dessus à la mise en place (2026-10-10). Elle ne peut que rétrécir :
  la commande porte elle-même les 20 noms de ce jour-là et refuse tout autre
  nom dans la liste.
- **Quand ça rougit** : seulement dans la pull request qui change les durées
  enregistrées ou la liste, donc celle qui rafraîchit les durées
  (`./bin/ci-test-seconds`, puis `./bin/ci-test-ceiling prune`). Un fichier
  devenu plus rapide ou plus lent ne rend rouge aucune autre pull request.
- **Sorties** : 0, une ligne ; 1, une raison par ligne sur stderr, chacune
  avec son fichier ; 2, usage. `--root <dossier>` fait lire un autre arbre
  (les tests l'emploient sur un arbre fabriqué).
- **Limites** : un fichier jamais mesuré par la CI n'a pas de plafond avant
  le rafraîchissement suivant ; les durées bougent avec la charge de l'hôte ;
  la qualité d'une raison n'est pas jugée par la commande.

Détail : `docs/TEST_GUIDELINE.md`.

---
