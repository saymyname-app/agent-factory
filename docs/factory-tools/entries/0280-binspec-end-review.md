## `./bin/spec-end-review` — le diff assemblé d'une Spec a-t-il été relu, et qu'a dit la revue ?

**La revue de code de fin** (Spec af-wf4w5r §6 « Fin de Spec », §9 point 4,
T25). Deux tickets, corrects chacun, peuvent se contredire une fois
assemblés : aucune revue par ticket ne le voit. Quand la porte de fin de
Spec a rendu ses trois verdicts mécaniques sur un commit, le flux — jamais
un auteur — envoie **tout le diff de la branche d'intégration contre la
branche protégée** à une session neuve du rôle relecteur, en lecture seule.
Ne concerne qu'un convoi qui porte la **marque du nouveau flux**.

```bash
./bin/spec-end-review show <convoi>      # où en est la revue de fin : passes, demande, arrêt, tour compté ; n'écrit rien
./bin/spec-end-review settle <convoi>    # ce qui est dû ; lancé par ./bin/convoy-advance à chaque passe
```

- **Mêmes règles que la revue d'un ticket** : un constat ne bloque que s'il
  cite une ligne de la Spec, d'un ticket du convoi ou une règle écrite du
  dépôt, et que du code retrouve cette ligne dans sa source. L'issue est
  calculée, jamais donnée par le relecteur.
- **Un Blocking Finding devient un ticket `repair`** rédigé par le
  relecteur ; `./bin/convoy-advance` le publie par la porte des tickets
  ajoutés et il suit le flux d'un ticket ordinaire. Pas de « corrigé /
  contesté » à la fin.
- **Rejouée en entier à chaque nouvelle pointe** : le `repair` fusionné
  déplace la pointe, la porte rejoue ses verdicts et une autre session relit
  tout le diff. Un verdict d'un tour précédent n'est jamais réutilisé.
- **La porte de fin de Spec refuse sans elle** : revue absente, en cours,
  arrêtée, liée à un autre commit, ou avec un Blocking Finding
  (`./bin/spec-end check` dit lequel).
- **Une sortie incomplète compte non passée** : un axe ou un fichier du diff
  non relu, pas de sortie dans le délai (7200 s, sans base mesurée), bead
  fermé sans sortie. Une relance, puis la revue est arrêtée et te remonte
  une fois (`./bin/escalation-door list`). Chaque passe garde sa durée et
  les fichiers non relus.
- **Un tour de fin est compté** par revue défavorable, une fois par pointe
  (`counters.end_rounds`).
- **Indépendance** : `show` dit si le relecteur tourne sur le modèle d'un
  auteur, ou si un modèle n'est pas relevé.
- **Limites** : les constats restent le jugement d'un agent ; la couverture
  est déclarée par le relecteur ; rien ne lève un arrêt de la revue sur sa
  pointe ; le compteur de tours n'est pas encore comparé à une borne.
- **En même temps que l'Outcome Evaluation** : la passe qui rend les trois
  verdicts lance les deux sur le même commit ; aucune n'attend l'autre.

Détail : `docs/SPEC_END_REVIEW.md`.

---
