## `./bin/factory-fix-preflight` — qui d'autre change ces fichiers ?

**À lancer avant de coder un correctif d'usine, puis avant d'ouvrir sa PR**
(af-frflvz, `docs/DELIVERY.md`). Le 19/10, la #681 a rendu la fidélité
bloquante alors que Benjamin venait de décider le contraire dans une autre
session (af-hcriwn). La #682 a défait la #681 une heure après sa fusion.

```bash
./bin/factory-fix-preflight bin/ticket-exit bin/ticket-end formulas/   # un fichier, ou un dossier finissant par /
```

- **Arrêt (sortie 1)** : une PR ouverte qui change ces chemins, une branche
  distante avec un commit des 2 derniers jours (`--days`) qui les change,
  ou un bead de décision récent qui les cite. Ne sont pas comptées la branche
  du correctif lui-même, ni celles dont toutes les PR sont fusionnées ou
  fermées.
- **À lire** (`decisions_to_read`) : chaque décision ouverte ou mise à jour
  pendant ces jours, même si elle ne cite aucun fichier, ce qui est le cas
  le plus courant. S'arrêter si l'une d'elles touche le correctif.
- **Refus (sortie 2)** : git, `gh pr list` ou `gc bd list` illisible. Un
  refus n'est jamais lu comme « rien trouvé ». L'outil n'écrit rien.

---
