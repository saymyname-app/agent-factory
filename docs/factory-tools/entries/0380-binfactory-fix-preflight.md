## `./bin/factory-fix-preflight` — qui d'autre change ces fichiers, et où ailleurs est ce défaut ?

**À lancer avant de coder un correctif d'usine, puis avant d'ouvrir sa PR**
(af-frflvz, `docs/DELIVERY.md`). Le 19/10, la #681 a rendu la fidélité
bloquante alors que Benjamin venait de décider le contraire dans une autre
session (af-hcriwn). La #682 a défait la #681 une heure après sa fusion.

```bash
./bin/factory-fix-preflight --class P bin/ticket-exit bin/ticket-end formulas/   # un fichier, ou un dossier finissant par /
```

- **Arrêt (sortie 1)** : une PR ouverte qui change ces chemins, une branche
  distante avec un commit des 2 derniers jours (`--days`) qui les change,
  ou un bead de décision récent qui les cite. Ne sont pas comptées la branche
  du correctif lui-même, ni celles dont toutes les PR sont fusionnées ou
  fermées.
- **À lire** (`decisions_to_read`) : chaque décision ouverte ou mise à jour
  pendant ces jours, même si elle ne cite aucun fichier, ce qui est le cas
  le plus courant. S'arrêter si l'une d'elles touche le correctif.
- **Où ailleurs ? (`--class`, obligatoire, af-npz9v1.25)** : le code de la
  catégorie du défaut dans `docs/DEFECT_CLASSES.md`. La réponse donne
  l'invariant et les occurrences encore ouvertes de la catégorie, à corriger
  avec le cas observé, et lance son contrôle (`control`) : un contrôle rouge
  est un arrêt (sortie 1). Une catégorie absente du registre est refusée :
  le correctif ajoute d'abord son entrée dans sa branche.
- **Refus (sortie 2)** : git, `gh pr list`, `gc bd list` ou le registre
  illisible. Un refus n'est jamais lu comme « rien trouvé ». L'outil
  n'écrit rien.

---
