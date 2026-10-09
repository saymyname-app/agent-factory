## `./bin/tdd-step` — les tests ont-ils été écrits d'abord ?

Un script le prouve, pas l'auteur (Spec af-wf4w5r §5, T10). Pour un ticket
d'un convoi qui porte la **marque du nouveau flux**, chaque étape vérifie la
branche du ticket à son dernier commit, enregistre son rapport comme pièce
du magasin de preuves, puis inscrit l'étape sur le ticket.

```bash
./bin/tdd-step red <convoi> <ticket> --repo <worktree> --profile <descripteur> --dataset <jeu> --base <commit de départ> --table <table critère → test>
./bin/tdd-step freeze <convoi> <ticket> --repo <worktree>
./bin/tdd-step green <convoi> <ticket> --repo <worktree> --profile <descripteur> --dataset <jeu>
./bin/tdd-step amend <convoi> <ticket> --repo <worktree> --profile <descripteur> --dataset <jeu> --reason "<raison>"
./bin/tdd-step prefactoring <convoi> <ticket> --repo <worktree> --profile <descripteur> --base <commit de départ>
```

- **Rouge** : seul le périmètre de test a changé depuis le commit de départ,
  chaque critère a un test, le produit lancé au commit de départ est en bonne
  santé, chaque test échoue par assertion et passe par un point d'entrée du
  produit. Un test en erreur, vide, ou qui ne demande rien au produit est
  refusé et nommé. Chaque test est prouvé selon le **mode du seam** par
  lequel il passe (boîte noire ou règle d'import, déclaré par seam dans le
  profil) ; le relevé nomme le seam et le mode de chaque test.
- **Critère déjà vert** : le ticket est arrêté (sortie 5), le critère est
  nommé, l'arrêt est écrit dans le tracker.
- **Gel** : refusé tant que le relecteur de tests n'a pas passé chaque test
  de critère, au même commit et sur les mêmes empreintes
  (`./bin/test-review`) ; ensuite les empreintes des tests, de la table et
  du harnais vont dans le magasin de preuves, hors de tout dépôt Git.
- **Vert** : refus si un fichier gelé a été modifié, supprimé ou déplacé ;
  sinon les tests gelés passent k fois de suite (k du profil ; 3 s'il n'en
  déclare pas). Un résultat mixte nomme le test instable.
- **Amendement** : le seul moyen de changer un test gelé, une fois par
  ticket, avec sa raison ; nouveau rouge, nouveau gel, diff enregistré. Le
  second arrête le ticket (sortie 5).
- **Prefactoring** : pas d'étape rouge ; la commande de régression passe
  avant et après ; aucun test existant n'est modifié.
- **Sorties** : 0 étape prouvée ; 1 refus, rien n'est écrit ; 4 « pas un
  convoi du nouveau flux » ; 5 ticket arrêté.
- **Limite** : le script prouve l'ordre et les résultats, pas qu'un test
  observe bien son critère : c'est la question du relecteur de tests, posée
  entre le rouge et le gel (`./bin/test-review`). Lever un arrêt n'est pas
  dans cette commande.

Détail : `docs/TDD_STEP.md`.

---

